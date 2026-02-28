from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout as auth_logout
from django.db import transaction as db_transaction, IntegrityError
from django.db.utils import OperationalError
from django.core.exceptions import ValidationError
from django.conf import settings
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin, urlparse, parse_qs
import logging
import re
import threading

import requests
from bs4 import BeautifulSoup

from .forms import ClientForm, ProfileForm, TopUpBalanceForm
from .models import Client, Profile, Package, Transaction, IPTVInfo, ClientPackageInfo
from .automation import auto_add_client_only, auto_buy_packages, check_client_exists_on_dealer, log_info, log_error
from .telegram_notify import notify_purchase, notify_error

logger = logging.getLogger(__name__)

IPTV_CHANNELS_DEFAULT = 1214


def _add_client_background(client_data: dict, user_id: int):
    """
    🔄 Асинхронная синхронизация клиента с сайтом дилера.
    Клиент уже существует в БД, синхронизируем его с дилером.
    
    Стратегия:
    1. Сначала пробуем requests (быстрее, без браузера)
    2. Если не сработает, пробуем Selenium
    
    Args:
        client_data: {"username": str, "password": str, "subscription": str}
        user_id: ID пользователя для логирования
    """
    from django.utils import timezone
    from clients.automation import auto_add_client_requests, auto_add_client_only
    
    username = client_data['username']
    
    try:
        logger.info(f"[SYNC] Начинаем синхронизацию клиента {username} с дилером...")
        
        # Обновляем статус: синхронизация началась
        client = Client.objects.get(username=username)
        client.dealer_sync_status = Client.SYNC_IN_PROGRESS
        client.save(update_fields=['dealer_sync_status'])
        
        # Стратегия 1: Пробуем requests (быстрее и надёжнее)
        logger.info(f"[SYNC] Пробуем метод 1: HTTP requests...")
        result = auto_add_client_requests(
            client_data['username'],
            client_data['password'],
            client_data.get('subscription', "Новый клиент")
        )
        
        if not result["ok"]:
            # Если requests не сработал, пробуем Selenium
            logger.info(f"[SYNC] Метод 1 не сработал, пробуем метод 2: Selenium...")
            result = auto_add_client_only(
                client_data['username'],
                client_data['password'],
                client_data.get('subscription', "Новый клиент")
            )
        
        logger.info(f"[SYNC] Результат синхронизации {username}: {result}")
        
        # Обновляем статус в зависимости от результата
        if result["ok"]:
            client.dealer_sync_status = Client.SYNC_SUCCESS
            client.dealer_sync_message = result.get('message', 'Успешно синхронизирован')
            client.dealer_synced_at = timezone.now()
            logger.info(f"[SYNC] ✅ {username} успешно синхронизирован с дилером!")
        else:
            # Проверяем тип ошибки
            error_message = result["message"].lower()
            
            if any(phrase in error_message for phrase in [
                "пользователь с таким логином существует",
                "пользователь уже существует",
                "логин занят",
                "уже зарегистрирован",
                "уже существует"
            ]):
                # Клиент уже существует на дилере - это тоже успех
                client.dealer_sync_status = Client.SYNC_SUCCESS
                client.dealer_sync_message = "Клиент уже существует на дилере"
                client.dealer_synced_at = timezone.now()
                logger.info(f"[SYNC] ℹ️ {username} уже существует на дилере")
            else:
                # Другая ошибка
                client.dealer_sync_status = Client.SYNC_FAILED
                client.dealer_sync_message = result['message'][:500]  # Ограничиваем длину
                logger.warning(f"[SYNC] ⚠️ Ошибка синхронизации {username}: {result['message']}")
        
        client.save(update_fields=['dealer_sync_status', 'dealer_sync_message', 'dealer_synced_at'])
    
    except Client.DoesNotExist:
        logger.error(f"[SYNC] ❌ Клиент {username} не найден в БД для синхронизации")
    except Exception as e:
        logger.exception(f"[SYNC] ❌ Ошибка при синхронизации {username}: {e}")
        try:
            client = Client.objects.get(username=username)
            client.dealer_sync_status = Client.SYNC_FAILED
            client.dealer_sync_message = f"Ошибка: {str(e)[:500]}"
            client.save(update_fields=['dealer_sync_status', 'dealer_sync_message'])
        except:
            pass


def _first_link_matching(links: List[str], include_terms: List[str], exclude_terms: Optional[List[str]] = None):
    exclude_terms = exclude_terms or []
    for href in links:
        lower = href.lower()
        if all(term in lower for term in include_terms) and not any(term in lower for term in exclude_terms):
            return href
    return None


def _find_labeled_link(soup: BeautifulSoup, labels: List[str]):
    for node in soup.find_all(string=True):
        text = (node or "").strip()
        if not text:
            continue
        lower = text.lower()
        if any(label in lower for label in labels):
            parent = node.parent
            for candidate in (parent.find("a"), parent.find_next("a")):
                if candidate and candidate.get("href"):
                    return candidate.get("href")
    return None


def _clean_number(text: str) -> str:
    cleaned = re.sub(r"[^\d.,]", "", text or "")
    return cleaned.replace(" ", "")


def _parse_int(text: str):
    cleaned = _clean_number(text)
    if not cleaned:
        return None
    try:
        return int(float(cleaned.replace(",", ".")))
    except (ValueError, TypeError):
        return None


def _parse_decimal(text: str):
    cleaned = _clean_number(text)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned.replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_iptv_page(html: str, username: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    all_links = [a.get("href") for a in soup.find_all("a") if a.get("href")]

    standard_link = _find_labeled_link(soup, ["стандарт", "standard"]) or _first_link_matching(all_links, ["get.php", "username"]) or (all_links[0] if all_links else None)
    short_link = _find_labeled_link(soup, ["коротк", "short"]) or _first_link_matching(all_links, ["/s/"]) or _first_link_matching(all_links, ["short"]) or None
    m3u8_link = _find_labeled_link(soup, ["m3u8"]) or _first_link_matching(all_links, ["m3u8"]) or None
    m3u_link = _find_labeled_link(soup, ["m3u"]) or _first_link_matching(all_links, ["m3u"], exclude_terms=["m3u8"]) or None
    spark_link = _find_labeled_link(soup, ["spark", "спарк"]) or _first_link_matching(all_links, ["spark"]) or None

    # Токен IPTV: сначала ищем в скриптах, затем в параметрах ссылок
    token = None
    script_text = " ".join(soup.find_all(string=re.compile("clientToken")))
    token_match = re.search(r"clientToken\s*=\s*[\"']([A-Za-z0-9]+)[\"']", script_text or "")
    if token_match:
        token = token_match.group(1)
    if not token:
        for href in all_links:
            parsed = urlparse(href)
            query_token = parse_qs(parsed.query).get("token", [None])[0]
            if query_token:
                token = query_token
                break

    total_channels = IPTV_CHANNELS_DEFAULT
    for text in soup.stripped_strings:
        lower = text.lower()
        if "канал" in lower or "channel" in lower:
            match = re.search(r"(\d{3,5})", text)
            if match:
                total_channels = int(match.group(1))
                break

    stats = {
        "active_subscribers": None,
        "activated_per_day": None,
        "activated_per_week": None,
        "unused_funds": None,
    }

    for row in soup.find_all("tr"):
        row_text = " ".join(row.stripped_strings)
        lower = row_text.lower()
        if "активных абонентов" in lower or "active subscribers" in lower:
            stats["active_subscribers"] = _parse_int(row_text)
        elif "за сутки" in lower or "per day" in lower:
            stats["activated_per_day"] = _parse_int(row_text)
        elif "за неделю" in lower or "per week" in lower:
            stats["activated_per_week"] = _parse_int(row_text)
        elif "непотраченных" in lower or "unused" in lower:
            stats["unused_funds"] = _parse_decimal(row_text)

    return {
        "standard_link": standard_link,
        "short_link": short_link,
        "m3u8_link": m3u8_link,
        "m3u_link": m3u_link,
        "spark_link": spark_link,
        "token": token,
        "active_subscribers": stats.get("active_subscribers"),
        "activated_per_day": stats.get("activated_per_day"),
        "activated_per_week": stats.get("activated_per_week"),
        "unused_funds": stats.get("unused_funds"),
        "total_channels": total_channels,
    }


def fetch_iptv_info(username: str) -> dict:
    if not settings.DEALER_URL or not settings.DEALER_LOGIN or not settings.DEALER_PASSWORD:
        raise ValueError("DEALER_URL/LOGIN/PASSWORD не настроены")

    base_url = settings.DEALER_URL.rstrip("/")
    session = requests.Session()

    login_payload = {
        "field_login": settings.DEALER_LOGIN,
        "field_password": settings.DEALER_PASSWORD,
        "submit_login": "Login",
    }

    def _parse_from_html(html: str):
        return parse_iptv_page(html, username)

    # Попытка 1: через requests
    try:
        login_resp = session.get(base_url, timeout=20)
        login_resp.raise_for_status()
        login_resp = session.post(base_url, data=login_payload, timeout=20)
        login_resp.raise_for_status()

        iptv_url = f"{base_url}/iptv_server.php?selected_user={username}"
        resp = session.get(iptv_url, timeout=25)
        resp.raise_for_status()
        parsed = _parse_from_html(resp.text)
    except Exception as exc:
        logger.warning("HTTP fetch IPTV failed (%s), fallback to Selenium", exc)
        parsed = None

    # Попытка 2: fallback через Selenium (если не получилось)
    if not parsed:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException
            from webdriver_manager.chrome import ChromeDriverManager

            local_lib_dir = "/home/tajshara/tools/libs/libasound2/usr/lib/x86_64-linux-gnu"
            if os.path.isdir(local_lib_dir):
                os.environ["LD_LIBRARY_PATH"] = f"{local_lib_dir}:{os.environ.get('LD_LIBRARY_PATH', '')}".rstrip(":")

            options = Options()
            cft_chrome = "/home/tajshara/tools/chrome-for-testing/chrome-linux64/chrome"
            cft_driver = "/home/tajshara/tools/chrome-for-testing/chromedriver-linux64/chromedriver"

            if os.path.exists(cft_chrome):
                options.binary_location = cft_chrome
            elif os.path.exists("/usr/bin/google-chrome"):
                options.binary_location = "/usr/bin/google-chrome"
            elif os.path.exists("/usr/bin/chromium-browser"):
                options.binary_location = "/usr/bin/chromium-browser"
            elif os.path.exists("/snap/chromium/current/usr/lib/chromium-browser/chrome"):
                options.binary_location = "/snap/chromium/current/usr/lib/chromium-browser/chrome"

            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--remote-debugging-port=9222")
            options.add_argument("--user-data-dir=/tmp/chrome-profile")
            options.add_argument("--disable-features=VizDisplayCompositor")

            if os.path.exists(cft_driver):
                service = Service(cft_driver)
            else:
                service = Service(ChromeDriverManager().install())

            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(40)
            try:
                driver.get(base_url)
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "field_login")))
                driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
                driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
                driver.find_element(By.NAME, "submit_login").click()

                iptv_url = f"{base_url}/iptv_server.php?selected_user={username}"
                driver.get(iptv_url)
                try:
                    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "a")))
                except TimeoutException:
                    pass
                html = driver.page_source
                parsed = _parse_from_html(html)
            finally:
                driver.quit()
        except Exception as exc:
            logger.exception("Selenium fallback for IPTV failed: %s", exc)
            raise

    if not parsed:
        raise ValueError("Не удалось получить IPTV данные: ни HTTP, ни Selenium")

    def absolute_link(link: str | None):
        if not link:
            return None
        return urljoin(base_url + "/", link)

    return {
        "standard_link": absolute_link(parsed.get("standard_link")),
        "short_link": absolute_link(parsed.get("short_link")),
        "m3u8_link": absolute_link(parsed.get("m3u8_link")),
        "m3u_link": absolute_link(parsed.get("m3u_link")),
        "spark_link": absolute_link(parsed.get("spark_link")),
        "token": parsed.get("token"),
        "active_subscribers": parsed.get("active_subscribers"),
        "activated_per_day": parsed.get("activated_per_day"),
        "activated_per_week": parsed.get("activated_per_week"),
        "unused_funds": parsed.get("unused_funds"),
        "total_channels": parsed.get("total_channels") or IPTV_CHANNELS_DEFAULT,
    }


def ensure_iptv_info(client: Client) -> Optional[IPTVInfo]:
    try:
        return client.iptv_info
    except IPTVInfo.DoesNotExist:
        pass
    except OperationalError as exc:
        logger.warning("IPTVInfo table is missing: %s", exc)
        return None

    data = fetch_iptv_info(client.username)

    try:
        iptv_info = IPTVInfo.objects.create(
            client=client,
            standard_link=data.get("standard_link"),
            short_link=data.get("short_link"),
            m3u8_link=data.get("m3u8_link"),
            m3u_link=data.get("m3u_link"),
            spark_link=data.get("spark_link"),
            token=data.get("token"),
            active_subscribers=data.get("active_subscribers"),
            activated_per_day=data.get("activated_per_day"),
            activated_per_week=data.get("activated_per_week"),
            unused_funds=data.get("unused_funds"),
            total_channels=data.get("total_channels") or IPTV_CHANNELS_DEFAULT,
        )
    except OperationalError as exc:
        logger.warning("Failed to create IPTVInfo due to DB error: %s", exc)
        return None

    return iptv_info

# 🔎 Проверка: может ли пользователь работать как менеджер
def is_client_manager(user):
    """Проверяет, имеет ли пользователь права менеджера"""
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name="Client Managers").exists())

# 🔒 Проверка: является ли пользователь администратором
def is_admin(user):
    """Проверяет, является ли пользователь администратором"""
    return user.is_authenticated and user.is_superuser

# 🚪 Выход из системы
def logout_view(request):
    """Выход пользователя из системы"""
    auth_logout(request)
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url:
        return redirect(next_url)
    # После выхода отправляем на страницу логина
    return redirect('login')

# 🏠 Главная страница
@login_required
def home_view(request):
    from .models import Announcement
    
    announcements = Announcement.objects.filter(is_active=True).order_by('order')
    context = {
        'announcements': announcements,
    }
    
    # Добавляем объявления в контекст через процессор контекста
    return render(request, "home.html", context)

# ➕ Добавление клиента (СТРОГО СИНХРОННО)
@login_required
@user_passes_test(is_client_manager)
def add_client_view(request):
    """
    Строгое добавление клиента:
    1. Сначала добавляет клиента на сайте дилера
    2. Только после успеха сохраняет в локальной БД
    """
    if request.method == "POST":
        form = ClientForm(request.POST)
        if form.is_valid():
            try:
                from django.utils import timezone
                from .automation import auto_add_client_requests

                # Проверяем, существует ли клиент с таким логином в нашей базе
                username = form.cleaned_data['username']
                if Client.objects.filter(username=username).exists():
                    messages.error(
                        request,
                        f"❌ Клиент с логином '{username}' уже существует в вашей базе данных. "
                        f"Пожалуйста, используйте другой логин или отредактируйте существующего клиента."
                    )
                    logger.warning(f"Attempt to add duplicate client {username} by {request.user.username}")
                    return render(request, "add_client.html", {"form": form})
                
                # ШАГ 1: ДОБАВЛЯЕМ НА САЙТ ДИЛЕРА
                client_data = {
                    "username": form.cleaned_data["username"],
                    "password": form.cleaned_data["password"],
                    "subscription": form.cleaned_data.get("subscription") or "Новый клиент",
                }
                dealer_result = auto_add_client_requests(
                    client_data["username"],
                    client_data["password"],
                    client_data["subscription"],
                )

                if not dealer_result.get("ok"):
                    logger.warning(
                        f"Dealer HTTP sync failed for {username}: {dealer_result.get('message')}"
                    )
                    dealer_result = auto_add_client_only(
                        client_data["username"],
                        client_data["password"],
                        client_data["subscription"],
                    )

                if not dealer_result.get("ok"):
                    messages.error(request, f"❌ {dealer_result.get('message', 'Ошибка на сайте дилера')}")
                    logger.warning(
                        f"Dealer sync failed for {username}: {dealer_result.get('message')}"
                    )
                    return render(request, "add_client.html", {"form": form})

                # ШАГ 2: СОХРАНЯЕМ В БД ТОЛЬКО ПОСЛЕ УСПЕХА НА ДИЛЕРЕ
                with db_transaction.atomic():
                    client = form.save(commit=False)
                    client.created_by = request.user
                    client.dealer_sync_status = Client.SYNC_SUCCESS
                    client.dealer_sync_message = dealer_result.get("message", "Успешно добавлен на дилере")
                    client.dealer_synced_at = timezone.now()
                    client.save()

                messages.success(
                    request,
                    f"✅ Клиент '{username}' добавлен на дилере и сохранен в системе."
                )
                logger.info(f"Client {username} added on dealer and saved locally")
                return redirect("clients_list")
                    
            except IntegrityError as e:
                if 'unique constraint' in str(e).lower() or 'username' in str(e).lower():
                    messages.error(
                        request,
                        f"❌ Клиент с логином '{form.cleaned_data['username']}' уже существует. "
                        f"Используйте другой логин."
                    )
                    logger.error(f"IntegrityError adding client {form.cleaned_data['username']}: {e}")
                else:
                    messages.error(request, f"❌ Ошибка базы данных: {str(e)}")
                    logger.exception(f"Database error adding client: {e}")
            except ValidationError as e:
                messages.error(request, f"❌ Ошибка валидации: {e}")
                logger.error(f"Validation error adding client: {e}")
            except Exception as e:
                messages.error(request, f"❌ Непредвиденная ошибка: {str(e)}")
                logger.exception(f"Error adding client: {e}")
        else:
            messages.error(request, "❌ Проверьте правильность заполнения формы")
    else:
        form = ClientForm()

    return render(request, "add_client.html", {"form": form})

# 📊 Список клиентов
@login_required
def clients_list_view(request):
    """Отображение списка клиентов с возможностью фильтрации"""
    # Суперпользователь видит всех клиентов, остальные - только своих
    if request.user.is_superuser:
        clients = Client.objects.select_related('created_by').all()
    else:
        clients = Client.objects.filter(created_by=request.user).select_related('created_by')
    
    # Оптимизация запросов
    clients = clients.order_by("-created_at")
    
    context = {
        "clients": clients,
        "total_count": clients.count(),
    }
    return render(request, "clients_list.html", context)

# ✏️ Редактирование клиента
@login_required
@user_passes_test(is_client_manager)
def edit_client(request, client_id):
    """Редактирование данных клиента"""
    client = get_object_or_404(Client, id=client_id)
    
    # Проверка прав доступа (не суперпользователи могут редактировать только своих клиентов)
    if not request.user.is_superuser and client.created_by != request.user:
        messages.error(request, "❌ У вас нет прав для редактирования этого клиента")
        return redirect("clients_list")
    
    if request.method == "POST":
        try:
            client.username = request.POST.get("username", "").strip()
            client.password = request.POST.get("password", "").strip()
            client.phone = request.POST.get("phone", "").strip()
            client.info = request.POST.get("info", "").strip()
            
            if not client.username or not client.password:
                raise ValidationError("Логин и пароль обязательны для заполнения")
            
            client.save()
            messages.success(request, "✏️ Данные клиента успешно обновлены!")
            logger.info(f"Client {client.username} updated by {request.user.username}")
            return redirect("clients_list")
            
        except ValidationError as e:
            messages.error(request, f"❌ {str(e)}")
        except Exception as e:
            messages.error(request, f"❌ Ошибка при сохранении: {str(e)}")
            logger.exception(f"Error updating client {client_id}: {e}")
            
    return render(request, "edit_client.html", {"client": client})

# ⚙️ Настройки клиента (объединено с edit_client для упрощения)
@login_required
@user_passes_test(is_client_manager)
def client_settings(request, client_id):
    """Дополнительные настройки клиента"""
    client = get_object_or_404(Client, id=client_id)
    
    # Проверка прав доступа
    if not request.user.is_superuser and client.created_by != request.user:
        messages.error(request, "❌ У вас нет прав для редактирования этого клиента")
        return redirect("clients_list")
    
    if request.method == "POST":
        # Обработка обновления информации
        if request.POST.get("action") == "update_info":
            try:
                client.info = request.POST.get("info", "").strip()
                client.save()
                messages.success(request, "⚙️ Настройки клиента успешно обновлены!")
                logger.info(f"Client settings for {client.username} updated by {request.user.username}")
                return redirect("clients_list")
            except Exception as e:
                messages.error(request, f"❌ Ошибка: {str(e)}")
                logger.exception(f"Error updating client settings for {client_id}: {e}")
        
        # Принудительная перезагрузка IPTV данных (только при явном клике)
        elif request.POST.get("action") == "refresh_iptv":
            try:
                # Удаляем старую запись если есть
                try:
                    old_info = client.iptv_info
                    old_info.delete()
                except (IPTVInfo.DoesNotExist, OperationalError):
                    pass
                
                # Получаем свежие данные
                iptv_info = ensure_iptv_info(client)
                if iptv_info:
                    messages.success(request, "✅ IPTV данные обновлены с сайта дилера")
                else:
                    messages.warning(request, "⚠️ Не удалось получить IPTV данные")
            except Exception as e:
                messages.error(request, f"❌ Ошибка при обновлении IPTV: {e}")
                logger.exception(f"Error refreshing IPTV info for {client.username}: {e}")
    
    # При загрузке страницы (GET) не запускаем браузер — показываем только кэшированные данные из БД
    iptv_info = None
    package_info = None
    try:
        iptv_info = client.iptv_info
    except (IPTVInfo.DoesNotExist, OperationalError):
        iptv_info = None
    
    try:
        package_info = client.package_info
    except (ClientPackageInfo.DoesNotExist, OperationalError):
        package_info = None
            
    return render(request, "client_settings.html", {"client": client, "iptv_info": iptv_info, "package_info": package_info})

# 👤 Профиль менеджера
@login_required
@user_passes_test(is_client_manager)
def client_manager_profile_view(request):
    """Отображение профиля менеджера с балансом и статистикой"""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    # Обновляем скидку на основе текущего количества клиентов
    profile.update_discount()
    
    # Статистика менеджера
    total_clients = Client.objects.filter(created_by=request.user).count()
    active_clients = Client.objects.filter(
        created_by=request.user, 
        end_date__gte=datetime.now().date()
    ).count()
    
    context = {
        "user": request.user,
        "profile": profile,
        "total_clients": total_clients,
        "active_clients": active_clients,
    }
    return render(request, "profile.html", context)

# ✏️ Редактирование телефона менеджера
@login_required
@user_passes_test(is_client_manager)
def edit_profile_view(request):
    """Редактирование профиля менеджера"""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "📱 Телефон успешно обновлён!")
                logger.info(f"Profile updated for user {request.user.username}")
                return redirect("client_manager_profile")
            except Exception as e:
                messages.error(request, f"❌ Ошибка при сохранении: {str(e)}")
                logger.exception(f"Error updating profile: {e}")
        else:
            messages.error(request, "❌ Проверьте правильность заполнения формы")
    else:
        form = ProfileForm(instance=profile)
        
    return render(request, "edit_profile.html", {"form": form})

# 💰 Пополнение баланса менеджера (свой баланс)
@login_required
@user_passes_test(is_client_manager)
def topup_balance_view(request):
    """Страница создания заявки на пополнение баланса"""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    # Получаем настройки платежей
    from .models import PaymentSettings, TopupRequest
    import requests
    
    payment_methods_qs = PaymentSettings.objects.all().order_by('-updated_at')
    payment_methods = list(payment_methods_qs)
    payment_settings = payment_methods[0] if payment_methods else None
    
    # Получаем курс TJS к USD в реальном времени
    from django.utils import timezone
    exchange_rate = Decimal('11.50')  # Курс по умолчанию
    exchange_rate_updated = None
    
    try:
        # API для получения курса валют
        response = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Получаем курс TJS к USD
            tjs_rate = data.get('rates', {}).get('TJS', 11.50)
            exchange_rate = Decimal(str(tjs_rate))
            exchange_rate_updated = timezone.now()  # Время успешного обновления
            logger.info(f"Exchange rate fetched successfully: 1 USD = {exchange_rate} TJS")
    except Exception as e:
        logger.warning(f"Could not fetch exchange rate: {e}")
    
    if request.method == "POST":
        try:
            amount_tjs_str = request.POST.get("amount_tjs", "0").strip()
            amount_tjs = Decimal(amount_tjs_str)
            transaction_proof = request.POST.get("transaction_proof", "").strip()
            
            if amount_tjs <= 0:
                messages.error(request, "❌ Сумма должна быть больше нуля!")
                return redirect('topup_balance')
            
            # Конвертируем в доллары
            amount_usd = amount_tjs / exchange_rate
            
            # Создаём заявку на пополнение
            topup_request = TopupRequest.objects.create(
                manager=request.user,
                amount_tjs=amount_tjs,
                amount_usd=amount_usd,
                exchange_rate=exchange_rate,
                transaction_proof=transaction_proof,
                status='pending'
            )

            # Telegram уведомление админу
            from .telegram_notify import notify_topup_request
            notify_topup_request(
                manager_username=request.user.username,
                amount_usd=float(amount_usd),
                amount_tjs=float(amount_tjs),
                request_id=topup_request.id,
                transaction_proof=transaction_proof
            )

            messages.success(
                request,
                f"✅ Заявка #{topup_request.id} создана! Сумма: {amount_tjs} TJS (≈ ${amount_usd:.2f}). "
                f"Ожидайте одобрения администратора."
            )
            logger.info(f"Topup request created: {request.user.username} - {amount_tjs} TJS")
            return redirect('client_manager_profile')
            
        except (InvalidOperation, ValueError):
            messages.error(request, "❌ Неверный формат суммы. Используйте числа")
        except Exception as e:
            messages.error(request, f"❌ Ошибка при создании заявки: {e}")
            logger.exception(f"Error creating topup request: {e}")
    
    # Получаем последние заявки пользователя
    recent_requests = TopupRequest.objects.filter(
        manager=request.user
    ).order_by('-created_at')[:5]
    
    context = {
        'profile': profile,
        'current_balance': profile.balance,
        'payment_settings': payment_settings,
        'payment_methods': payment_methods,
        'exchange_rate': exchange_rate,
        'exchange_rate_updated': exchange_rate_updated,
        'recent_requests': recent_requests,
    }
    return render(request, "topup_balance.html", context)


# 📊 История баланса менеджера
@login_required
@user_passes_test(is_client_manager)
def balance_history_view(request):
    """Страница истории операций с балансом менеджера"""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    # Получаем все транзакции менеджера
    transactions = Transaction.objects.filter(
        manager=request.user
    ).select_related('client').order_by('-created_at')
    
    # Разделяем на пополнения и покупки
    topups = transactions.filter(client__isnull=True, total_cost__lt=0)
    purchases = transactions.filter(client__isnull=False, total_cost__gt=0)
    
    context = {
        'profile': profile,
        'transactions': transactions,
        'topups': topups,
        'purchases': purchases,
        'total_topups': sum(abs(t.total_cost) for t in topups),
        'total_purchases': sum(t.total_cost for t in purchases),
    }
    return render(request, "balance_history.html", context)


# 📦 Выбор пакетов (основная покупка)
@login_required
@user_passes_test(is_client_manager)
def select_packages_view(request):
    """Покупка пакетов для клиента с автоматическим расчётом стоимости"""
    prefill_username = request.GET.get("client", "")
    
    # Получаем список клиентов текущего менеджера
    if request.user.is_superuser:
        clients = Client.objects.all().order_by('username')
    else:
        clients = Client.objects.filter(created_by=request.user).order_by('username')

    packages = Package.objects.all().order_by('name')
    
    # IPTV: при загрузке страницы (GET) показываем ВСЕ пакеты, без запуска браузера
    # Браузер запустим только при явном клике "Обновить список" (POST с action=refresh_packages)

    if request.method == "POST" and request.POST.get("action") == "refresh_packages":
        # Пользователь явно нажал кнопку "Обновить список" - запускаем браузер
        if getattr(settings, 'USE_DEALER_PACKAGES', False):
            target_username = request.POST.get("username", "").strip()
            if target_username:
                try:
                    from .automation import get_available_packages
                    dealer_names = [p['value'] for p in get_available_packages(target_username)]
                    if dealer_names:
                        packages = packages.filter(name__in=dealer_names)
                        messages.info(request, f"✅ Список пакетов обновлён для {target_username}")
                except Exception as e:
                    logger.warning(f"Не удалось получить список пакетов с дилера для {target_username}: {e}")
                    messages.warning(request, f"⚠️ Не удалось обновить список: {e}")
        return render(request, "packages.html", {"packages": packages, "prefill_username": target_username, "clients": clients, "today": datetime.now().date().isoformat()})

    if request.method == "POST":
        try:
            username = request.POST.get("username", "").strip()
            selected = request.POST.getlist("selected_packages")
            start_date_str = request.POST.get("start_date")
            end_date_str = request.POST.get("end_date")

            # Логирование для отладки
            debug_msg = f"DEBUG: POST форма получена - username='{username}', start_date='{start_date_str}', end_date='{end_date_str}', packages={selected}"
            log_info(debug_msg)

            # Валидация данных
            if not username:
                raise ValidationError("Введите логин клиента")
            
            if not selected:
                raise ValidationError("Выберите хотя бы один пакет")
            
            if not start_date_str or not end_date_str:
                raise ValidationError("Укажите даты начала и окончания")

            # Поиск клиента
            client = Client.objects.filter(username=username).first()
            if not client:
                messages.error(request, f"❌ Клиент '{username}' не найден")
                return redirect("select_packages")
            
            # Проверка прав доступа
            if not request.user.is_superuser and client.created_by != request.user:
                raise ValidationError("У вас нет прав для покупки пакетов этому клиенту")

            # Расчёт количества дней
            start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            
            if start > end:
                raise ValidationError("Дата начала не может быть позже даты окончания")
            
            days = max(1, (end - start).days)

            # Расчёт стоимости по дням
            total_cost = Decimal("0.00")
            selected_packages_list = []
            
            for pkg in packages:
                if pkg.name in selected:
                    selected_packages_list.append(pkg.name)
                    monthly = Decimal(str(pkg.price))
                    daily = monthly / Decimal(30)
                    total_cost += daily * Decimal(days)

            # Применяем скидку менеджера (автоматическая + ручная)
            profile, _ = Profile.objects.get_or_create(user=request.user)
            manager_discount = profile.get_total_discount()  # Возвращает скидку в %
            if manager_discount > 0:
                discount_amount = total_cost * Decimal(manager_discount) / Decimal(100)
                total_cost -= discount_amount

            is_iptv_selected = any("iptv" in name.lower() for name in selected_packages_list)

            # Округление до 2 знаков
            total_cost = total_cost.quantize(Decimal("0.01"))

            # Проверка баланса менеджера
            if total_cost > profile.balance:
                messages.error(
                    request, 
                    f"❌ Недостаточно средств. Стоимость: {total_cost}$, баланс: {profile.balance}$"
                )
                return redirect("select_packages")

            # 🤖 СТРОГИЙ СИНХРОННЫЙ РЕЖИМ: Сначала покупка на сайте дилера
            log_info(f"[STRICT SYNC] Начинаем покупку на дилере для {client.username} на {days} дней")
            # ✅ На дилер передаём ПРАВИЛЬНОЕ количество дней (30, 180 или 365)
            # Дилер автоматически распределит подписку на этот период
            auto_result = auto_buy_packages(
                client.username,
                package_names=selected_packages_list,
                days=days  # 🔹 Передаём выбранное количество дней (30, 180 или 365)
            )
            
            # Проверяем результат покупки на дилере
            if not auto_result["ok"]:
                # ❌ Покупка на дилере НЕ удалась - отменяем операцию
                log_error(f"[STRICT SYNC] Покупка на дилере не удалась: {auto_result.get('message')}")
                messages.error(
                    request,
                    f"❌ Покупка отменена. Ошибка на сайте дилера: {auto_result.get('message', 'Неизвестная ошибка')}"
                )
                # 📱 Отправить уведомление об ошибке
                notify_error(
                    error_title="Покупка пакетов не удалась",
                    error_msg=f"Клиент: {client.username}, Ошибка: {auto_result.get('message', 'Неизвестная ошибка')}"
                )
                return redirect("select_packages")
            
            # ✅ Покупка на дилере успешна - сохраняем в нашу БД
            log_info(f"[STRICT SYNC] Покупка на дилере успешна, сохраняем в БД")
            
            # Выполнение транзакции в нашей БД
            with db_transaction.atomic():
                # Списываем деньги у менеджера
                profile.balance -= total_cost
                profile.save()

                # Сохраняем пакеты клиенту
                client.subscription = ", ".join(selected_packages_list)
                client.start_date = start
                client.end_date = end
                client.save()

                # Сохраняем транзакцию
                Transaction.objects.create(
                    manager=request.user,
                    client=client,
                    packages=", ".join(selected_packages_list),
                    total_cost=total_cost,
                    days_purchased=days
                )
            
            log_info(f"[STRICT SYNC] Транзакция сохранена в БД")
            
            # 📦 📺 Сохраняем IPTV информацию из результата auto_buy_packages
            # (браузер и данные уже получены, дополнительные запусы браузера вызывают ошибки)
            if auto_result.get("iptv_data"):
                try:
                    iptv_info, _ = IPTVInfo.objects.get_or_create(client=client)
                    data = auto_result.get("iptv_data", {})
                    iptv_info.standard_link = data.get("standard_link", "")
                    iptv_info.short_link = data.get("short_link", "")
                    iptv_info.m3u8_link = data.get("m3u8_link", "")
                    iptv_info.m3u_link = data.get("m3u_link", "")
                    iptv_info.spark_link = data.get("spark_link", "")
                    if data.get("token"):
                        iptv_info.token = data.get("token")
                    if data.get("active_subscribers") is not None:
                        iptv_info.active_subscribers = data.get("active_subscribers")
                    if data.get("activated_per_day") is not None:
                        iptv_info.activated_per_day = data.get("activated_per_day")
                    if data.get("activated_per_week") is not None:
                        iptv_info.activated_per_week = data.get("activated_per_week")
                    if data.get("unused_funds") is not None:
                        iptv_info.unused_funds = data.get("unused_funds")
                    iptv_info.total_channels = data.get("total_channels", 0)
                    iptv_info.save()
                    logger.info(f"IPTV info updated for {client.username}")
                except Exception as e:
                    logger.warning(f"Failed to save IPTV info for {client.username}: {e}")

            # 📱 Отправить Telegram уведомление
            notify_purchase(
                username=client.username,
                subscription=client.subscription,
                cost=float(total_cost)
            )

            messages.success(
                request,
                f"✅ Куплены пакеты: {client.subscription} для {client.username}. "
                f"Списано {total_cost}$ с баланса."
            )
            
            logger.info(
                f"Packages purchased by {request.user.username} "
                f"for client {client.username}: {total_cost}$ | "
                f"Automation: {auto_result['message']}"
            )
            return redirect("clients_list")
            
        except ValueError as e:
            messages.error(request, f"❌ Ошибка формата данных: {str(e)}")
        except ValidationError as e:
            messages.error(request, f"❌ {str(e)}")
        except Exception as e:
            messages.error(request, f"❌ Непредвиденная ошибка: {str(e)}")
            logger.exception(f"Error in select_packages_view: {e}")

    context = {
        "packages": packages, 
        "prefill_username": prefill_username,
        "clients": clients,
        "today": datetime.now().date().isoformat(),
    }
    return render(request, "packages.html", context)


# 💰 Пополнение баланса менеджера (только для админов)
@login_required
def admin_topup_balance_view(request):
    """Пополнение баланса менеджера администратором"""
    from django.http import JsonResponse
    from decimal import Decimal, InvalidOperation
    import json
    
    logger.info(f"admin_topup_balance_view called: method={request.method}, user={request.user.username}, path={request.path}")
    
    # Проверка прав доступа
    if not request.user.is_superuser:
        logger.warning(f"Access denied for user {request.user.username}: not superuser")
        if request.method == "POST" and request.POST.get('profile_id'):
            return JsonResponse({
                'success': False,
                'message': 'У вас нет прав для выполнения этой операции'
            }, status=403)
        else:
            return redirect('admin:login')
    
    if request.method == "POST":
        # Проверяем, является ли это AJAX запросом
        is_ajax = request.POST.get('profile_id') is not None or (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        )
        
        if is_ajax:
            # Обработка AJAX запроса
            try:
                profile_id = request.POST.get('profile_id')
                amount = request.POST.get('amount')
                comment = request.POST.get('comment', '')
                
                logger.info(f"Topup request: profile_id={profile_id}, amount={amount}, user={request.user.username}")
                
                if not profile_id or not amount:
                    return JsonResponse({
                        'success': False,
                        'message': 'Отсутствуют обязательные параметры'
                    }, status=400)
                
                try:
                    amount = Decimal(amount)
                except (InvalidOperation, ValueError):
                    return JsonResponse({
                        'success': False,
                        'message': 'Некорректная сумма'
                    }, status=400)
                    
                if amount <= 0:
                    return JsonResponse({
                        'success': False,
                        'message': 'Сумма должна быть больше нуля'
                    }, status=400)
                
                profile = Profile.objects.get(id=profile_id)
                
                with db_transaction.atomic():
                    # Пополняем баланс
                    old_balance = profile.balance
                    profile.balance += amount
                    profile.save()
                    
                    # Создаём транзакцию пополнения
                    Transaction.objects.create(
                        manager=profile.user,
                        client=None,
                        packages=f"Пополнение баланса администратором {request.user.username}",
                        total_cost=-amount,
                        days_purchased=0,
                        comment=comment or "Пополнение баланса"
                    )
                    
                    logger.info(
                        f"Admin {request.user.username} topped up {profile.user.username} "
                        f"balance: +{amount}$ (comment: {comment})"
                    )
                    
                    # Telegram уведомление админу
                    from .telegram_notify import notify_topup_balance
                    notify_topup_balance(
                        manager_username=profile.user.username,
                        amount=float(amount),
                        old_balance=float(old_balance),
                        new_balance=float(profile.balance)
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'Баланс пополнен на {amount}$',
                        'new_balance': float(profile.balance)
                    })
                    
            except Profile.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Профиль не найден'
                }, status=404)
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': 'Некорректная сумма'
                }, status=400)
            except Exception as e:
                logger.exception(f"Error in admin_topup_balance_view: {e}")
                return JsonResponse({
                    'success': False,
                    'message': f'Ошибка: {str(e)}'
                }, status=500)
        else:
            # Обработка обычной формы
            form = TopUpBalanceForm(request.POST)
            if form.is_valid():
                try:
                    with db_transaction.atomic():
                        profile = form.cleaned_data['manager']
                        amount = form.cleaned_data['amount']
                        comment = form.cleaned_data.get('comment', '')
                        
                        # Пополняем баланс
                        old_balance = profile.balance
                        profile.balance += amount
                        profile.save()
                        
                        # Создаём транзакцию пополнения
                        Transaction.objects.create(
                            manager=profile.user,
                            client=None,  # Нет клиента для транзакций пополнения
                            packages=f"Пополнение баланса администратором {request.user.username}",
                            total_cost=-amount,  # Отрицательная сумма = пополнение
                            days_purchased=0,
                            comment=comment or "Пополнение баланса"
                        )
                        
                        messages.success(
                            request,
                            f"✅ Баланс менеджера {profile.user.username} пополнен на {amount}$. "
                            f"Было: {old_balance}$, стало: {profile.balance}$"
                        )
                        logger.info(
                            f"Admin {request.user.username} topped up {profile.user.username} "
                            f"balance: +{amount}$ (comment: {comment})"
                        )
                        # Telegram уведомление админу
                        from .telegram_notify import notify_topup_balance
                        notify_topup_balance(
                            manager_username=profile.user.username,
                            amount=float(amount),
                            old_balance=float(old_balance),
                            new_balance=float(profile.balance)
                        )
                        return redirect('admin_topup_balance')
                        
                except Exception as e:
                    messages.error(request, f"❌ Ошибка при пополнении баланса: {str(e)}")
                    logger.exception(f"Error in admin_topup_balance_view: {e}")
    else:
        form = TopUpBalanceForm()
    
    # Получаем список всех менеджеров с их балансами
    profiles = Profile.objects.select_related('user').all().order_by('user__username')
    
    context = {
        'form': form,
        'profiles': profiles,
    }
    return render(request, 'admin_topup_balance.html', context)


# 🎁 Управление ручными скидками менеджеров (только для администраторов)
@login_required
@user_passes_test(is_admin)
def admin_manage_discounts_view(request):
    """Представление для управления ручными скидками менеджеров"""
    from .forms import ManualDiscountForm
    
    if request.method == "POST":
        profile_id = request.POST.get('profile_id')
        try:
            profile = Profile.objects.get(id=profile_id)
            form = ManualDiscountForm(request.POST, instance=profile)
            
            if form.is_valid():
                old_discount = profile.manual_discount_percentage
                old_total = profile.get_total_discount()
                
                form.save()
                new_total = profile.get_total_discount()
                
                messages.success(
                    request,
                    f"✅ Ручная скидка менеджера {profile.user.username} обновлена на {profile.manual_discount_percentage}%. "
                    f"Итоговая скидка: {old_total}% → {new_total}%"
                )
                logger.info(
                    f"Admin {request.user.username} set manual discount for {profile.user.username}: "
                    f"{old_discount}% → {profile.manual_discount_percentage}%"
                )
        except Profile.DoesNotExist:
            messages.error(request, "❌ Профиль менеджера не найден")
        except Exception as e:
            messages.error(request, f"❌ Ошибка при изменении скидки: {str(e)}")
            logger.exception(f"Error in admin_manage_discounts_view: {e}")
    
    # Получаем список всех менеджеров с их скидками
    profiles = Profile.objects.select_related('user').all().order_by('user__username')
    
    context = {
        'profiles': profiles,
        'form': ManualDiscountForm(),
    }
    return render(request, 'admin_manage_discounts.html', context)

def csrf_failure(request, reason=''):
    return render(request, 'csrf_failure.html', {'reason': reason}, status=403)


# 🔄 Синхронизация пакетов с сайта дилера
@login_required
@user_passes_test(is_admin)
def sync_packages_from_dealer_view(request):
    """Синхронизация пакетов с сайта дилера в БД"""
    if request.method == "POST":
        username = request.POST.get('username', 'demo')
        
        # Импортируем функцию синхронизации
        from django.core.management import call_command
        from io import StringIO
        
        try:
            # Вызываем команду синхронизации
            out = StringIO()
            call_command('sync_packages_from_dealer', '--username', username, stdout=out)
            
            # Парсим результат
            output = out.getvalue()
            
            messages.success(request, f"✅ Синхронизация завершена для клиента {username}")
            return redirect('clients_list')
            
        except Exception as e:
            messages.error(request, f"❌ Ошибка синхронизации: {str(e)}")
            logger.exception(f"Error in sync_packages_from_dealer_view: {e}")
            return redirect('clients_list')
    
    # GET запрос - показываем форму
    clients = Client.objects.all().order_by('username')
    return render(request, 'sync_packages.html', {'clients': clients})


@login_required
def ports_table_view(request):
    """📋 Таблица портов (независимая от пакетов)"""
    from .models import PortInfo
    
    ports = PortInfo.objects.all().order_by('package_name')
    
    context = {
        'ports': ports,
    }
    
    return render(request, 'ports_table.html', context)