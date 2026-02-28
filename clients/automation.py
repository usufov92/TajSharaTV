import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from django.conf import settings
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Константы
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 60
SHORT_TIMEOUT = 60
PAGE_LOAD_TIMEOUT = 10  # Не ждём полной загрузки с 'none' стратегией
ELEMENT_WAIT_TIMEOUT = 30
RETRY_DELAY = 10  # Ждать 10 секунд между попытками

# Используем именованный логгер, чтобы маршрутизировать через Django dictConfig
logger = logging.getLogger("automation")


def _create_session_with_retries():
    """Создаёт сессию requests с автоматическими повторами"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],  # Изменен параметр
        backoff_factor=1
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
    })
    return session


def auto_add_client_requests(client_username: str, client_password: str, subscription: str = "") -> dict:
    """
    ➕ Добавление клиента используя requests (БЕЗ SELENIUM).
    Строгий режим: сначала добавляем на дилере, затем проверяем наличие в index.php.
    
    Args:
        client_username: Логин клиента
        client_password: Пароль клиента
        subscription: Комментарий к клиенту
    
    Returns:
        dict: {"ok": bool, "message": str}
    """
    result = {"ok": False, "message": ""}
    
    try:
        # Получаем URL дилера
        base_url = _get_dealer_url()
        if not base_url:
            result["message"] = "DEALER_URL не настроен"
            return result

        log_info(f"[REQUESTS] Добавляем клиента {client_username}...")

        # Создаём сессию
        session = _create_session_with_retries()

        # Шаг 1: Открываем базовую страницу для установки cookies/ssn
        base_response = session.get(f"{base_url}/", timeout=10)
        ssn = None
        try:
            parsed = urlparse(base_response.url)
            ssn = parse_qs(parsed.query).get("ssn", [None])[0]
        except Exception:
            ssn = None

        def _with_ssn(url: str) -> str:
            if not ssn:
                return url
            return f"{url}?ssn={ssn}"

        # Шаг 2: Авторизуемся через login.php
        log_info("[REQUESTS] Авторизуемся...")
        response = session.post(
            _with_ssn(f"{base_url}/login.php"),
            data={
                "field_login": settings.DEALER_LOGIN,
                "field_password": settings.DEALER_PASSWORD,
                "submit_login": "Войти",
            },
            timeout=10,
            allow_redirects=True,
        )
        log_debug(f"[REQUESTS] Login response: {response.status_code}")

        # Проверяем доступ на index.php
        index_response = session.get(
            _with_ssn(f"{base_url}/index.php"),
            timeout=10,
            allow_redirects=True,
        )
        if "login.php" in (index_response.url or ""):
            result["message"] = "Ошибка авторизации на дилере"
            log_error(f"[REQUESTS] {result['message']}")
            return result

        # Шаг 2-3: Добавляем клиента и проверяем наличие (с повтором)
        client_data = {
            "login": client_username,
            "password_new": client_password,
            "password_confirm": client_password,
            "notice": subscription,
            "server_n": "1",
            "save": "Сохранить",
        }
        for attempt in range(1, 3):
            log_info(f"[REQUESTS] Отправляем форму добавления клиента (попытка {attempt}/2)...")
            response = session.post(
                _with_ssn(f"{base_url}/add.php"),
                data=client_data,
                timeout=10,
                allow_redirects=True,
            )

            if "login.php" in (response.url or ""):
                result["message"] = "Нет доступа к форме добавления клиента"
                log_error(f"[REQUESTS] {result['message']}")
                return result

            if response.status_code != 200:
                result["message"] = f"HTTP ошибка {response.status_code}"
                log_error(f"[REQUESTS] {result['message']}")
                return result

            log_debug(f"[REQUESTS] Ответ сервера: {len(response.text)} байт")

            verify_response = session.get(
                _with_ssn(f"{base_url}/index.php"),
                timeout=10,
                allow_redirects=True,
            )
            if "login.php" in (verify_response.url or ""):
                result["message"] = "Ошибка авторизации на дилере"
                log_error(f"[REQUESTS] {result['message']}")
                return result

            if client_username in verify_response.text:
                result["ok"] = True
                result["message"] = "Клиент добавлен на дилере"
                log_info(f"[REQUESTS] ✅ Клиент {client_username} найден на дилере")
                return result

            log_info("[REQUESTS] Клиент не найден, повторяем проверку...")
            time.sleep(2)

        result["message"] = "База данных даёт сбой"
        log_error(f"[REQUESTS] {result['message']}")

    except requests.Timeout:
        result["message"] = "Таймаут при соединении с сайтом дилера"
        log_error(result["message"])
    except requests.RequestException as e:
        result["message"] = f"Ошибка сети: {str(e)}"
        log_error(result["message"])
    except Exception as e:
        result["message"] = f"Ошибка: {str(e)[:200]}"
        log_exception(result["message"], e)

    return result


def _get_dealer_url() -> str | None:
    """Возвращает корректный базовый URL дилера или None если не настроен."""
    url = getattr(settings, "DEALER_URL", None)
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url:
        return None
    return url.rstrip("/")


def _page_info(driver) -> str:
    try:
        return f"url={driver.current_url} title={driver.title}"
    except Exception:
        return "url/title unavailable"


def _build_driver(headless: bool = True, page_load_strategy: str = 'normal'):
    """Создаёт Chrome WebDriver с преднастроенными опциями.
    
    Args:
        headless: Запускать в headless режиме
        page_load_strategy: 'normal', 'eager', или 'none'
            - 'normal': ждёт полной загрузки страницы (по умолчанию)
            - 'eager': ждёт DOMContentLoaded, но не все ресурсы
            - 'none': не ждёт загрузки страницы
    """
    import os
    options = ChromeOptions()

    local_lib_dir = "/home/tajshara/tools/libs/libasound2/usr/lib/x86_64-linux-gnu"
    
    # Стратегия загрузки страницы
    options.page_load_strategy = page_load_strategy
    if os.path.isdir(local_lib_dir):
        os.environ["LD_LIBRARY_PATH"] = f"{local_lib_dir}:{os.environ.get('LD_LIBRARY_PATH', '')}".rstrip(":")

    cft_chrome = "/home/tajshara/tools/chrome-for-testing/chrome-linux64/chrome"
    cft_driver = "/home/tajshara/tools/chrome-for-testing/chromedriver-linux64/chromedriver"

    # Приоритет: системные браузеры (более стабильны на Linux), затем Chrome for Testing
    if os.path.exists("/usr/bin/chromium-browser"):
        options.binary_location = "/usr/bin/chromium-browser"
    elif os.path.exists("/usr/bin/google-chrome"):
        options.binary_location = "/usr/bin/google-chrome"
    elif os.path.exists(cft_chrome):
        options.binary_location = cft_chrome
    elif os.path.exists("/snap/chromium/current/usr/lib/chromium-browser/chrome"):
        options.binary_location = "/snap/chromium/current/usr/lib/chromium-browser/chrome"

    user_data_dir = getattr(settings, "CHROME_USER_DATA_DIR", "")
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")

    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--disable-features=VizDisplayCompositor")
        # Ускорение загрузки страниц
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-sync")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-translate")
        options.add_argument("--no-default-browser-check")
        # Для Linux - попытка избежать краша
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--single-process")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-component-extensions-with-background-pages")
        options.add_argument("--disable-preconnect")
        # Anti-detection
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

    # Подбор chromedriver
    if os.path.exists(cft_driver):
        service = ChromeService(cft_driver)
    else:
        chromedriver_path = getattr(settings, "CHROMEDRIVER_PATH", None)
        if chromedriver_path and os.path.exists(chromedriver_path):
            service = ChromeService(chromedriver_path)
        else:
            service = ChromeService(ChromeDriverManager().install())

    return webdriver.Chrome(service=service, options=options)

def log_info(message: str):
    """Логирование информационного сообщения"""
    try:
        logger.info(message)
    except Exception:
        # fallback на корневой логгер если конфиг ещё не инициализирован
        logging.getLogger().info(message)

def log_error(message: str):
    """Логирование ошибки"""
    try:
        logger.error(message)
    except Exception:
        logging.getLogger().error(message)

def log_exception(message: str, exc: Exception):
    """Логирование исключения"""
    try:
        logger.exception(message)
    except Exception:
        logging.getLogger().exception(message)

def log_debug(message: str):
    """Логирование отладочной информации"""
    try:
        logger.debug(message)
    except Exception:
        logging.getLogger().debug(message)

def retry_on_failure(func, max_attempts=MAX_RETRIES, delay=2):
    """
    Декоратор для повторных попыток выполнения функции при ошибке
    """
    def wrapper(*args, **kwargs):
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_attempts:
                    raise
                log_info(f"Попытка {attempt} не удалась. Повторная попытка в {delay}с...")
                time.sleep(delay)
        return None
    return wrapper

def wait_and_click(driver, by, selector, timeout=DEFAULT_TIMEOUT, step_name="", scroll_to_element=True):
    """
    Универсальная функция ожидания и клика по элементу.
    
    Args:
        driver: WebDriver instance
        by: Метод поиска (By.CSS_SELECTOR, By.XPATH и т.д.)
        selector: Селектор элемента
        timeout: Время ожидания в секундах
        step_name: Название шага для логирования
        scroll_to_element: Прокручивать ли страницу к элементу
    
    Returns:
        bool: True если клик успешен, False иначе
    """
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        
        # Прокрутка к элементу если требуется
        if scroll_to_element:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)  # Небольшая пауза после прокрутки
        
        element.click()
        log_info(f"[SUCCESS] Успешно кликнули: {step_name or selector}")
        return True
        
    except TimeoutException:
        log_error(f"[TIMEOUT] Элемент не найден за {timeout}с: {step_name or selector}")
        return False
    except NoSuchElementException:
        log_error(f"[NOT_FOUND] Элемент не существует: {step_name or selector}")
        return False
    except Exception as e:
        log_error(f"[ERROR] Ошибка при клике на элемент: {step_name or selector} | {e}")
        log_debug(f"HTML snippet: {driver.page_source[:500]}")
        return False


def fetch_iptv_data_from_dealer(client_username: str) -> dict:
    """
    📺 Получить IPTV ссылки клиента со страницы /iptv_server.php дилера.
    
    Args:
        client_username: Логин клиента
    
    Returns:
        dict: {"ok": bool, "data": {...}, "html": str, "message": str}
    """
    driver = None
    result = {"ok": False, "data": {}, "html": "", "message": ""}

    try:
        driver = _build_driver(headless=True, page_load_strategy='none')
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_debug(f"[DEBUG] Получаем IPTV информацию для: {client_username}")

        base_url = _get_dealer_url()
        if not base_url:
            result["message"] = "DEALER_URL не настроен"
            log_error(f"[ERROR] {result['message']}")
            return result
        
        # Авторизация с retry logic
        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                driver.get(base_url)
                WebDriverWait(driver, SHORT_TIMEOUT).until(
                    EC.presence_of_element_located((By.NAME, "field_login"))
                )
                log_debug(f"[DEBUG] Страница авторизации загружена (попытка {attempt + 1})")
                break
            except (TimeoutException, WebDriverException) as e:
                log_error(f"[ERROR] Ошибка загрузки страницы (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    result["message"] = f"Ошибка авторизации после {max_retries} попыток: {e}"
                    log_error(f"[ERROR] {result['message']}")
                    return result
        
        try:
            driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
            driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
            driver.find_element(By.NAME, "submit_login").click()
            time.sleep(3)
            log_debug(f"[DEBUG] Авторизация выполнена")
        except Exception as e:
            result["message"] = f"Ошибка авторизации: {e}"
            log_error(f"[ERROR] {result['message']}")
            return result

        # Переход на страницу IPTV клиента
        iptv_url = f"{base_url}/iptv_server.php?selected_user={client_username}"
        log_debug(f"[DEBUG] Загружаем страницу IPTV: {iptv_url}")
        
        try:
            driver.get(iptv_url)
        except TimeoutException:
            log_debug(f"[DEBUG] Таймаут загрузки, но продолжаем работу")
        except Exception as e:
            result["message"] = f"Ошибка при загрузке страницы: {e}"
            log_error(f"[ERROR] {result['message']}")
            return result

        time.sleep(3)
        result["ok"] = True

        # Сохраняем HTML страницы в результат (без записи на диск)
        html_content = driver.page_source
        result["html"] = html_content

        # Парсим ссылки со страницы через BeautifulSoup
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")

            def _clean_number(text: str) -> str:
                import re
                cleaned = re.sub(r"[^\d.,]", "", text or "")
                return cleaned.replace(" ", "")

            def _parse_int(text: str):
                try:
                    cleaned = _clean_number(text)
                    if not cleaned:
                        return None
                    return int(float(cleaned.replace(",", ".")))
                except Exception:
                    return None

            def _parse_decimal(text: str):
                from decimal import Decimal
                try:
                    cleaned = _clean_number(text)
                    if not cleaned:
                        return None
                    return Decimal(cleaned.replace(",", "."))
                except Exception:
                    return None

            # Ищем все ссылки
            all_links = [a.get("href") for a in soup.find_all("a") if a.get("href")]

            # Токен сначала ищем в скриптах, потом в ссылках
            import re
            token = None
            script_text = " ".join(soup.find_all(string=re.compile("clientToken")))
            token_match = re.search(r"clientToken\s*=\s*[\"']([A-Za-z0-9]+)[\"']", script_text or "")
            if token_match:
                token = token_match.group(1)
            if not token:
                from urllib.parse import urlparse, parse_qs
                for href in all_links:
                    parsed = urlparse(href)
                    q_token = parse_qs(parsed.query).get("token", [None])[0]
                    if q_token:
                        token = q_token
                        break

            # Парсим каналы и ссылки
            total_channels = 1214  # по умолчанию
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

            result["data"] = {
                "standard_link": next((l for l in all_links if "get.php" in l or "username" in l), None),
                "short_link": next((l for l in all_links if "/s/" in l), None),
                "m3u8_link": next((l for l in all_links if "m3u8" in l), None),
                "m3u_link": next((l for l in all_links if "m3u" in l and "m3u8" not in l), None),
                "spark_link": next((l for l in all_links if "spark" in l.lower()), None),
                "token": token,
                "active_subscribers": stats.get("active_subscribers"),
                "activated_per_day": stats.get("activated_per_day"),
                "activated_per_week": stats.get("activated_per_week"),
                "unused_funds": stats.get("unused_funds"),
                "total_channels": total_channels,
            }

            log_debug(f"[DEBUG] Найдено IPTV ссылок: {sum(1 for v in result['data'].values() if v)}")
        except Exception as e:
            log_debug(f"[DEBUG] Ошибка при парсинге IPTV данных: {e}")

    except Exception as e:
        result["message"] = f"Непредвиденная ошибка: {e}"
        log_error(f"[ERROR] {result['message']}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    return result


def fetch_client_packages_info(client_username: str) -> dict:
    """
    📦 Получить информацию о текущих пакетах клиента со страницы /iptv_server.php?selected_user={client_username} дилера.
    
    Args:
        client_username: Логин клиента
    
    Returns:
        dict: {"ok": bool, "packages": list, "html": str, "message": str}
    """
    driver = None
    result = {"ok": False, "packages": [], "html": "", "message": ""}

    try:
        driver = _build_driver(headless=True)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_debug(f"[DEBUG] Получаем информацию о пакетах для: {client_username}")

        base_url = _get_dealer_url()
        if not base_url:
            result["message"] = "DEALER_URL не настроен"
            log_error(f"[ERROR] {result['message']}")
            return result
        
        # Авторизация
        try:
            driver.get(base_url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "field_login")))
            driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
            driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
            driver.find_element(By.NAME, "submit_login").click()
            time.sleep(2)
            log_debug(f"[DEBUG] Авторизация выполнена")
        except Exception as e:
            result["message"] = f"Ошибка авторизации: {e}"
            log_error(f"[ERROR] {result['message']}")
            return result

        # Переход на страницу пакетов клиента
        packets_url = f"{base_url}/iptv_server.php?selected_user={client_username}"
        log_debug(f"[DEBUG] Загружаем страницу пакетов: {packets_url}")
        
        try:
            driver.get(packets_url)
            time.sleep(4)
            result["ok"] = True
        except Exception as e:
            result["message"] = f"Ошибка при загрузке страницы: {e}"
            log_error(f"[ERROR] {result['message']}")
            return result

        # Сохраняем HTML страницы в результат (без записи на диск)
        html_content = driver.page_source
        result["html"] = html_content

        # Получаем список пакетов (с указанием выбранных)
        try:
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[name='user_packet_groups[]']")
            log_debug(f"[DEBUG] Найдено пакетов: {len(checkboxes)}")
            
            for cb in checkboxes:
                try:
                    value = cb.get_attribute("value")
                    is_checked = cb.is_selected()
                    
                    # Ищем label
                    label = "No label"
                    try:
                        label_elem = cb.find_element(By.XPATH, "following-sibling::label[1]")
                        label = label_elem.text.strip() if label_elem else value
                    except:
                        label = value
                    
                    result["packages"].append({
                        "value": value,
                        "label": label,
                        "checked": is_checked
                    })
                    log_debug(f"[DEBUG] Пакет: {value} (выбран: {is_checked})")
                except Exception as e:
                    log_debug(f"[DEBUG] Ошибка при парсинге пакета: {e}")
                    continue
        except Exception as e:
            log_debug(f"[DEBUG] Ошибка при получении пакетов: {e}")

        log_debug(f"[DEBUG] Всего пакетов получено: {len(result['packages'])}")

    except Exception as e:
        result["message"] = f"Непредвиденная ошибка: {e}"
        log_error(f"[ERROR] {result['message']}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    return result


def auto_add_client_only(client_username: str, client_password: str, subscription: str = "") -> dict:
    """
    ➕ ЧАСТЬ 1: Только добавление клиента на сайт дилера.
    
    Шаги:
    1. Авторизуется как дилер
    2. Переходит на страницу добавления клиента
    3. Заполняет логин, пароль и комментарий
    4. Сохраняет клиента
    5. Закрывает браузер
    
    Args:
        client_username: Логин клиента
        client_password: Пароль клиента
        subscription: Комментарий к клиенту (необязательно)
    
    Returns:
        dict: {"ok": bool, "message": str}
    """
    driver = None
    result = {"ok": False, "message": ""}

    try:
        log_info(f"[PART 1] Начинаем добавление клиента: {client_username}")
        
        # Получаем URL до создания драйвера
        base_url = _get_dealer_url()
        if not base_url:
            result["message"] = "DEALER_URL не настроен"
            log_error(f"[ERROR] {result['message']}")
            return result
        
        log_info(f"[INFO] URL дилера: {base_url}")

        # Шаг 1: Авторизация на сайте дилера
        log_info("[STEP 1] Авторизация на сайте дилера")
        log_info(f"[INFO] Открытие страницы {base_url}...")
        
        # Попытки с retry logic - СОЗДАЁМ НОВЫЙ DRIVER ДЛЯ КАЖДОЙ ПОПЫТКИ
        max_retries = MAX_RETRIES
        retry_delay = RETRY_DELAY
        ssn = None
        for attempt in range(max_retries):
            try:
                # Создаём новый WebDriver для каждой попытки
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                
                log_info(f"[INFO] Создание WebDriver (попытка {attempt + 1}/{max_retries})...")
                driver = _build_driver(headless=True, page_load_strategy='none')
                # Не устанавливаем page_load_timeout, так как 'none' не требует ожидания загрузки
                log_info(f"[INFO] WebDriver создан")

                try:
                    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                except Exception:
                    pass
                
                log_info(f"[INFO] Открытие страницы {base_url}...")
                # Используем try-except для игнорирования таймаутов загрузки страницы
                try:
                    driver.get(base_url)
                except TimeoutException:
                    log_info(f"[INFO] Timeout на page_load, но page_load_strategy='none' игнорирует - продолжаем")
                    pass
                
                log_info(f"[INFO] Команда driver.get() выполнена (попытка {attempt + 1})")
                log_info(f"[INFO] Ожидание формы логина (таймаут: {ELEMENT_WAIT_TIMEOUT}с)...")
                
                # Ждём появления формы логина (это значит страница загрузилась)
                WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                    EC.presence_of_element_located((By.NAME, "field_login"))
                )
                log_info(f"[SUCCESS] Страница загружена и форма логина найдена: {_page_info(driver)}")
                try:
                    ssn = parse_qs(urlparse(driver.current_url).query).get("ssn", [None])[0]
                except Exception:
                    ssn = None
                break
                
            except TimeoutException as te:
                log_error(f"[ERROR] Таймаут при загрузке {base_url} (попытка {attempt + 1}/{max_retries}): {te}")
                if attempt < max_retries - 1:
                    log_info(f"[INFO] Повторная попытка через {retry_delay}с...")
                    time.sleep(retry_delay)
                    continue
                else:
                    result["message"] = f"Превышено время ожидания загрузки сайта дилера после {max_retries} попыток"
                    return result
                    
            except WebDriverException as we:
                error_str = str(we).lower()
                # Проверяем "invalid session id"
                if "invalid session id" in error_str or "session not created" in error_str:
                    log_error(f"[ERROR] Chrome сессия потеряна/краш (попытка {attempt + 1}/{max_retries}): {we}")
                else:
                    log_error(f"[ERROR] Ошибка WebDriver при загрузке {base_url} (попытка {attempt + 1}/{max_retries}): {we}")
                
                if attempt < max_retries - 1:
                    log_info(f"[INFO] Повторная попытка через {retry_delay}с...")
                    time.sleep(retry_delay)
                    continue
                else:
                    result["message"] = f"Ошибка браузера после {max_retries} попыток: {str(we)[:200]}"
                    return result
        
        # Форма логина уже найдена в цикле выше, заполняем её
        driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
        driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
        driver.find_element(By.NAME, "submit_login").click()
        
        time.sleep(2)
        log_info("[SUCCESS] Авторизация выполнена")

        # Шаг 2: Переход к форме добавления клиента
        log_info("[STEP 2] Переход к форме добавления клиента")
        try:
            add_url = f"{base_url}/add.php"
            if ssn:
                add_url = f"{add_url}?ssn={ssn}"
            driver.get(add_url)
            time.sleep(2)
        except Exception as e:
            result["message"] = f"Не найдена страница добавления клиента: {e}"
            log_error(result["message"])
            return result

        time.sleep(1)

        # Шаг 3: Заполнение данных клиента
        log_info("[STEP 3] Заполнение формы клиента")
        try:
            WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.NAME, "login"))
            )
            
            driver.find_element(By.NAME, "login").send_keys(client_username)
            driver.find_element(By.NAME, "password_new").send_keys(client_password)
            driver.find_element(By.NAME, "password_confirm").send_keys(client_password)
            if subscription:
                driver.find_element(By.NAME, "notice").send_keys(subscription)

            # server_n select (если есть)
            try:
                server_select = Select(driver.find_element(By.NAME, "server_n"))
                server_select.select_by_value("1")
            except Exception:
                pass
            
            log_info("[SUCCESS] Форма заполнена")
            
        except NoSuchElementException as e:
            result["message"] = f"Не найдены поля формы: {e}"
            log_error(result["message"])
            return result

        # Шаг 4: Сохранение клиента
        log_info("[STEP 4] Сохранение клиента")
        try:
            save_button = driver.find_element(By.NAME, "save")
            save_button.click()
            time.sleep(2)
            log_info("[SUCCESS] Клиент сохранён")
            
        except NoSuchElementException:
            result["message"] = "Не найдена кнопка сохранения"
            log_error(result["message"])
            return result

        # Проверка ошибок
        error_elems = driver.find_elements(By.CSS_SELECTOR, "div#msg-error, .error-message")
        if error_elems:
            error_text = error_elems[0].text
            result["message"] = f"Клиент уже существует или ошибка: {error_text}"
            log_error(result["message"])
            return result

        # Шаг 5: Проверяем наличие клиента на index.php
        log_info("[STEP 5] Проверяем клиента на index.php")
        verify_url = f"{base_url}/index.php"
        if ssn:
            verify_url = f"{verify_url}?ssn={ssn}"
        try:
            driver.get(verify_url)
            time.sleep(2)
        except Exception as e:
            result["message"] = f"Ошибка проверки клиента: {e}"
            log_error(result["message"])
            return result

        page_source = (driver.page_source or "").lower()
        if client_username.lower() not in page_source:
            result["message"] = "База данных даёт сбой"
            log_error(result["message"])
            return result

        # ✅ Успешное завершение первой части
        log_info("[COMPLETE - PART 1] Клиент успешно добавлен!")
        result["ok"] = True
        result["message"] = "Клиент добавлен"

    except TimeoutException as e:
        result["message"] = f"Превышено время ожидания: {str(e)}"
        log_error(result["message"])
    except WebDriverException as e:
        result["message"] = f"Ошибка WebDriver: {str(e)}"
        log_error(result["message"])
    except Exception as e:
        result["message"] = f"Непредвиденная ошибка: {str(e)}"
        log_error(result["message"])
    finally:
        if driver:
            try:
                driver.quit()
                log_info("[CLEANUP] Браузер закрыт (Часть 1)")
            except:
                pass

    return result


def get_available_packages(client_username: str) -> list:
    """
    🔍 Получить список всех доступных пакетов на странице пакетов дилера.
    
    Args:
        client_username: Логин клиента
    
    Returns:
        list: Список {value, label} всех пакетов на странице
    """
    driver = None
    packages = []

    try:
        driver = _build_driver(headless=True, page_load_strategy='none')
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_debug(f"[DEBUG] Получаем доступные пакеты для: {client_username}")

        base_url = _get_dealer_url()
        if not base_url:
            log_error("[DEBUG] DEALER_URL не настроен")
            return []
        
        # Авторизация
        try:
            driver.get(base_url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "field_login")))
            driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
            driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
            driver.find_element(By.NAME, "submit_login").click()
            time.sleep(2)
        except Exception as e:
            log_error(f"[DEBUG] Ошибка авторизации при получении пакетов: {e}")
            return []

        # Переход на страницу пакетов (полный URL)
        packets_url = f"{base_url}/packets.php?selected_user={client_username}"
        log_debug(f"[DEBUG] Загружаем URL: {packets_url}")
        
        try:
            driver.get(packets_url)
            time.sleep(4)
        except Exception as e:
            log_error(f"[DEBUG] Ошибка при загрузке страницы пакетов: {e}")
            return []

        # Пытаемся найти checkboxes несколькими методами
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input[name='user_packet_groups[]']"))
            )
        except TimeoutException:
            log_debug(f"[DEBUG] Checkboxes не найдены за 10 сек, пробуем парсить HTML")

        # Метод 1: CSS selector
        try:
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[name='user_packet_groups[]']")
            if checkboxes:
                log_debug(f"[DEBUG] Найдено checkboxes (CSS): {len(checkboxes)}")
        except Exception as e:
            log_debug(f"[DEBUG] CSS selector не сработал: {e}")
            checkboxes = []

        # Метод 2: XPath если первый не помог
        if not checkboxes:
            try:
                checkboxes = driver.find_elements(By.XPATH, "//input[@name='user_packet_groups[]']")
                if checkboxes:
                    log_debug(f"[DEBUG] Найдено checkboxes (XPath): {len(checkboxes)}")
            except Exception as e:
                log_debug(f"[DEBUG] XPath selector не сработал: {e}")

        # Парсим найденные checkboxes
        for idx, cb in enumerate(checkboxes):
            try:
                value = cb.get_attribute("value")
                if not value:
                    continue
                    
                # Пытаемся найти label несколькими способами
                label = "No label"
                try:
                    # Способ 1: следующий sibling label
                    label_elem = cb.find_element(By.XPATH, "following-sibling::label[1]")
                    label = label_elem.text.strip() if label_elem else "No label"
                except:
                    try:
                        # Способ 2: родительский label
                        label_elem = cb.find_element(By.XPATH, "ancestor::label[1]")
                        label = label_elem.text.strip() if label_elem else "No label"
                    except:
                        # Способ 3: соседний текстовый узел
                        try:
                            label = cb.get_attribute("title") or value
                        except:
                            label = value
                
                packages.append({"value": value, "label": label})
                log_debug(f"[DEBUG] Пакет #{idx}: value='{value}', label='{label}'")
                
            except Exception as e:
                log_debug(f"[DEBUG] Ошибка при обработке checkbox #{idx}: {e}")
                continue

        log_debug(f"[DEBUG] Всего пакетов получено: {len(packages)}")

    except Exception as e:
        log_error(f"[ERROR] Ошибка при получении пакетов: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    return packages


def check_client_exists_on_dealer(client_username: str) -> dict:
    """
    Быстрый чек наличия клиента на сайте дилера (перед покупкой).
    Возвращает dict с ok/message. ok=False если клиент отсутствует/страница не загрузилась.
    """
    result = {"ok": False, "message": ""}
    driver = None
    try:
        driver = _build_driver(headless=True, page_load_strategy='none')
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

        log_info(f"[CHECK] Проверяем клиента {client_username} на сайте дилера")

        # Авторизация с retry logic
        base_url = _get_dealer_url()
        if not base_url:
            result["message"] = "DEALER_URL не настроен"
            log_error(result["message"])
            return result
        
        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                driver.get(base_url)
                WebDriverWait(driver, SHORT_TIMEOUT).until(
                    EC.presence_of_element_located((By.NAME, "field_login"))
                )
                break
            except (TimeoutException, WebDriverException) as e:
                log_error(f"[ERROR] Ошибка загрузки (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    result["message"] = f"Ошибка загрузки страницы после {max_retries} попыток"
                    log_error(result["message"])
                    return result
        
        try:
            driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
            driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
            driver.find_element(By.NAME, "submit_login").click()
            time.sleep(2)
        except Exception as e:
            result["message"] = f"Ошибка авторизации дилера: {e}"
            log_error(result["message"])
            return result

        # Открываем страницу пакетов конкретного клиента
        packets_url = f"{base_url}/packets.php?selected_user={client_username}"
        try:
            driver.get(packets_url)
        except Exception as e:
            result["message"] = f"Не удалось загрузить страницу: {e}"
            log_error(result["message"])
            return result

        time.sleep(5)

        # Проверяем, что страница загрузилась и содержит селект с пользователями
        try:
            options = driver.find_elements(By.CSS_SELECTOR, "select[name='selected_user'] option")
            option_values = [(opt.get_attribute("value") or opt.text or "").strip().lower() for opt in options]
            if not option_values:
                result["message"] = "Страница клиента не загрузилась или список пользователей пуст"
                log_error(result["message"])
                return result

            if client_username.lower() not in option_values:
                result["message"] = f"Клиент {client_username} не найден на билинг"
                log_error(result["message"])
                return result

            # Дополнительно убедимся, что текущий URL содержит выбранного клиента
            if client_username.lower() not in (driver.current_url or "").lower():
                result["message"] = f"Страница клиента не соответствует логину {client_username}"
                log_error(result["message"])
                return result

            result["ok"] = True
            result["message"] = "Клиент найден на сайте дилера"
            log_info(f"[CHECK OK] Клиент {client_username} найден на сайте дилера")
            return result

        except Exception as e:
            result["message"] = f"Ошибка при проверке клиента: {e}"
            log_error(result["message"])
            return result
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass


def auto_buy_packages(client_username: str, package_names: list = None, days: int = 365) -> dict:
    """
    💰 ЧАСТЬ 2: Покупка пакетов для клиента на сайте дилера.
    
    Шаги:
    1. Проверяет авторизацию (если не авторизован - авторизуется)
    2. Переходит прямо на страницу пакетов по URL
    3. Выбирает чекбокс пакета
    4. Выбирает срок подписки
    5. Нажимает "Купить"
    6. Закрывает браузер
    
    Args:
        client_username: Логин клиента
        package_names: Список названий пакетов для выбора (по value атрибуту)
        days: Количество дней для подписки (по умолчанию 365)
    
    Returns:
        dict: {"ok": bool, "message": str}
    """
    driver = None
    result = {"ok": False, "message": ""}

    try:
        driver = _build_driver(headless=True, page_load_strategy='none')
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_info(f"[PART 2] Начинаем покупку пакетов для клиента: {client_username}")

        # Шаг 1: Проверка и авторизация на сайте дилера
        base_url = _get_dealer_url()
        if not base_url:
            result["message"] = "DEALER_URL не настроен"
            log_error(result["message"])
            return result
        
        log_info("[STEP 1] Проверка авторизации")
        
        # Проверяем авторизацию - пытаемся перейти на главную страницу
        max_retries = 3
        retry_delay = 5
        is_authorized = False
        
        for attempt in range(max_retries):
            try:
                driver.get(base_url)
                time.sleep(2)
                
                # Проверяем, есть ли форма авторизации
                login_form = driver.find_elements(By.NAME, "field_login")
                
                if login_form:
                    log_info("[INFO] Требуется авторизация")
                    is_authorized = False
                    break
                else:
                    log_info("[SUCCESS] Авторизация уже выполнена")
                    is_authorized = True
                    break
                    
            except (TimeoutException, WebDriverException) as e:
                log_error(f"[ERROR] Ошибка проверки авторизации (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    result["message"] = f"Ошибка проверки авторизации после {max_retries} попыток"
                    log_error(result["message"])
                    return result
        
        # Если не авторизован - выполняем вход
        if not is_authorized:
            log_info("[STEP 2] Выполнение авторизации")
            try:
                driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
                driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
                driver.find_element(By.NAME, "submit_login").click()
                time.sleep(2)
                log_info("[SUCCESS] Вход выполнен успешно")
            except Exception as e:
                log_error(f"[ERROR] Ошибка при заполнении формы: {e}")
                result["message"] = f"Ошибка входа: {e}"
                return result
        else:
            log_info("[STEP 2] Авторизация не требуется, уже авторизован")

        # Шаг 3: Переход прямо на страницу пакетов (без промежуточных кликов)
        log_info(f"[STEP 3] Переход на пакеты клиента {client_username}")
        packets_url = f"{base_url}/packets.php?selected_user={client_username}"
        driver.get(packets_url)
        
        # Увеличиваем ожидание загрузки
        time.sleep(10)
        
        log_info("[SUCCESS] Страница пакетов пользователя загружена")
        
        # 🔍 ПРОВЕРКА: Убедимся что это страница правильного клиента
        try:
            # Проверяем URL - содержит ли он нужного клиента
            current_url = driver.current_url.lower()
            if client_username.lower() not in current_url:
                result["message"] = f"Ошибка: страница не принадлежит клиенту {client_username}. URL: {current_url}"
                log_error(f"[ERROR] {result['message']}")
                return result
            log_info(f"[SUCCESS] Проверка URL пройдена: страница принадлежит клиенту {client_username}")
            
            # Проверяем что на странице есть контент пакетов
            html_content_check = driver.page_source
            if len(html_content_check) < 1000:  # Минимальный размер HTML для валидной страницы
                result["message"] = f"Ошибка: страница клиента {client_username} пуста или не загружена"
                log_error(f"[ERROR] {result['message']}")
                return result
            log_info(f"[SUCCESS] Проверка контента пройдена: страница содержит данные")
            
        except Exception as e:
            result["message"] = f"Ошибка при проверке страницы клиента: {str(e)}"
            log_error(f"[ERROR] {result['message']}")
            return result
        
        # Проверяем наличие iframe
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                log_info(f"[DEBUG] Найдено iframe'ов: {len(iframes)}")
        except:
            pass
        
        # Дополнительное ожидание наличия элементов пакетов
        for attempt in range(3):
            try:
                checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[name='user_packet_groups[]']")
                if checkboxes:
                    log_info(f"[SUCCESS] Элементы пакетов найдены (попытка {attempt+1}): {len(checkboxes)} элементов")
                    break
                else:
                    log_info(f"[DEBUG] Попытка {attempt+1}: пакеты не найдены, ждём ещё...")
                    time.sleep(3)
            except Exception as e:
                log_info(f"[DEBUG] Попытка {attempt+1} ошибка: {e}")
                time.sleep(3)
        
        # Сохраняем HTML в переменную (без записи на диск)
        html_content = driver.page_source
        log_info("[SUCCESS] Страница пакетов открыта")

        # Шаг 3: Выбор чекбокса пакета
        log_info("[STEP 3] Выбор пакета")
        
        # Отладка: получаем все доступные пакеты через JavaScript
        try:
            all_packages_js = driver.execute_script("""
                let checkboxes = document.querySelectorAll("input[name='user_packet_groups[]']");
                let packages = [];
                checkboxes.forEach(cb => {
                    packages.push({value: cb.value, checked: cb.checked});
                });
                return packages;
            """)
            log_info(f"[DEBUG] Доступные пакеты на странице: {all_packages_js}")
        except Exception as e:
            log_info(f"[DEBUG] Не удалось получить пакеты через JS: {e}")
        
        # Логируем HTML элементов для отладки
        try:
            form_html = driver.execute_script("""
                let form = document.querySelector('form');
                return form ? {
                    action: form.action,
                    method: form.method,
                    inputs: Array.from(form.querySelectorAll('input')).map(i => ({
                        type: i.type,
                        name: i.name,
                        id: i.id,
                        value: i.value ? i.value.substring(0, 50) : '',
                        checked: i.checked
                    }))
                } : 'No form found';
            """)
            log_info(f"[DEBUG] Форма на странице: {form_html}")
        except Exception as e:
            log_info(f"[DEBUG] Ошибка при анализе формы: {e}")
        
        try:
            if not package_names:
                # Если пакеты не указаны, выбираем первый доступный
                log_info("[DEBUG] Выбираем первый доступный пакет")
                checkbox = driver.find_element(By.CSS_SELECTOR, "input[name='user_packet_groups[]']")
            else:
                # Выбираем по указанному value
                checkbox = None
                for pkg_name in package_names:
                    try:
                        log_info(f"[DEBUG] Ищем пакет с value='{pkg_name}'")
                        # Пытаемся несколько способов найти checkbox
                        try:
                            checkbox = driver.find_element(By.CSS_SELECTOR, f"input[name='user_packet_groups[]'][value='{pkg_name}']")
                            log_info(f"[SUCCESS] Найден пакет CSS-селектором: {pkg_name}")
                        except NoSuchElementException:
                            # Попытка через XPath
                            checkbox = driver.find_element(By.XPATH, f"//input[@name='user_packet_groups[]'][@value='{pkg_name}']")
                            log_info(f"[SUCCESS] Найден пакет XPath'ом: {pkg_name}")
                        break
                    except NoSuchElementException:
                        log_info(f"[DEBUG] Пакет '{pkg_name}' не найден ни CSS ни XPath")
                        continue
                
                if not checkbox:
                    result["message"] = f"Пакет не найден. Попробованы: {package_names}. Доступные: {all_packages_js if 'all_packages_js' in locals() else 'unknown'}"
                    log_error(result["message"])
                    return result
            
            # Scroll и click
            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
            time.sleep(1)
            
            # Логируем позицию элемента перед кликом
            checkbox_info = driver.execute_script("""
                let cb = arguments[0];
                return {
                    visible: cb.offsetParent !== null,
                    disabled: cb.disabled,
                    checked: cb.checked,
                    value: cb.value,
                    id: cb.id,
                    name: cb.name
                };
            """, checkbox)
            log_info(f"[DEBUG] Информация о чекбоксе перед кликом: {checkbox_info}")
            
            checkbox.click()
            log_info("[SUCCESS] Чекбокс пакета выбран")
            time.sleep(2)
            
        except Exception as e:
            result["message"] = f"Ошибка при выборе пакета: {e}"
            log_error(result["message"])
            return result

        # Шаг 4: Выбор срока подписки через дату окончания
        log_info(f"[STEP 4] Выбор срока подписки: {days} дн.")
        try:
            date_inputs = driver.find_elements(By.CSS_SELECTOR, "input#data1, input#data2")
            log_info(f"[DEBUG] Найдено полей с датой: {len(date_inputs)}")
            
            if len(date_inputs) >= 2:
                # Логируем текущие значения полей
                data1_val = driver.execute_script("return document.getElementById('data1')?.value || 'NOT FOUND'")
                data2_val = driver.execute_script("return document.getElementById('data2')?.value || 'NOT FOUND'")
                log_info(f"[DEBUG] Текущие значения: data1='{data1_val}', data2='{data2_val}'")
                
                driver.execute_script(
                    """
                    (function(days){
                        function pad(n){return n<10?'0'+n:n;}
                        function parseDMY(s){
                            var m = /^\s*(\d{2})-(\d{2})-(\d{4})\s*$/.exec(s||'');
                            if(!m) return null;
                            return new Date(parseInt(m[3],10), parseInt(m[2],10)-1, parseInt(m[1],10));
                        }
                        function formatDMY(d){
                            return pad(d.getDate())+'-'+pad(d.getMonth()+1)+'-'+d.getFullYear();
                        }
                        var startEl = document.getElementById('data1');
                        var endEl = document.getElementById('data2');
                        if(!startEl || !endEl) return false;
                        var start = parseDMY(startEl.value) || new Date();
                        var end = new Date(start.getTime());
                        end.setDate(end.getDate() + days);
                        endEl.value = formatDMY(end);
                        var dayCountEl = document.getElementById('day_count');
                        if(dayCountEl) dayCountEl.value = String(days);
                        if(typeof window.calcDays === 'function') {
                            window.calcDays();
                        }
                        return true;
                    })(arguments[0]);
                    """,
                    days,
                )
                
                # Логируем новые значения после установки
                data1_val_after = driver.execute_script("return document.getElementById('data1')?.value || 'NOT FOUND'")
                data2_val_after = driver.execute_script("return document.getElementById('data2')?.value || 'NOT FOUND'")
                log_info(f"[DEBUG] Новые значения: data1='{data1_val_after}', data2='{data2_val_after}'")
                
                log_info("[SUCCESS] Дата окончания установлена через поля data1/data2")
                time.sleep(2)
            else:
                log_info(f"[DEBUG] Полей data1/data2 не найдено, ищем ссылку периода...")
                period_text = f"{days} дн."
                element = driver.find_element(By.XPATH, f"//a[contains(text(),'{period_text}')]")
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                driver.execute_script("arguments[0].click();", element)
                log_info(f"[SUCCESS] Срок подписки выбран: {period_text}")
                time.sleep(2)
        except Exception as e:
            result["message"] = f"Ошибка при выборе срока: {e}"
            log_error(result["message"])
            return result

        # Шаг 5: Нажимаем кнопку "Купить"
        log_info("[STEP 5] Оформление покупки")
        try:
            # Логируем все кнопки submit на странице
            submit_buttons = driver.execute_script("""
                let buttons = document.querySelectorAll("input[name='submit'], input[type='submit'], button[type='submit']");
                return Array.from(buttons).map(b => ({
                    type: b.type,
                    name: b.name,
                    value: b.value,
                    id: b.id,
                    visible: b.offsetParent !== null
                }));
            """)
            log_info(f"[DEBUG] Найденные кнопки submit: {submit_buttons}")
            
            # Пытаемся найти кнопку "Купить"
            try:
                buy_button = driver.find_element(By.CSS_SELECTOR, "input[name='submit'][value='Купить']")
                log_info("[DEBUG] Кнопка 'Купить' найдена CSS селектором")
            except NoSuchElementException:
                # Попытка через XPath
                try:
                    buy_button = driver.find_element(By.XPATH, "//input[@name='submit'][@value='Купить']")
                    log_info("[DEBUG] Кнопка 'Купить' найдена XPath'ом")
                except NoSuchElementException:
                    # Попытка найти просто button
                    try:
                        buy_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Купить')]")
                        log_info("[DEBUG] Кнопка 'Купить' найдена как button")
                    except NoSuchElementException:
                        result["message"] = "Кнопка 'Купить' не найдена на странице"
                        log_error(result["message"])
                        return result
            
            # Логируем информацию о кнопке перед кликом
            button_info = driver.execute_script("""
                let btn = arguments[0];
                return {
                    visible: btn.offsetParent !== null,
                    disabled: btn.disabled,
                    value: btn.value,
                    text: btn.textContent
                };
            """, buy_button)
            log_info(f"[DEBUG] Информация о кнопке перед кликом: {button_info}")
            
            # Скролл к кнопке и клик
            driver.execute_script("arguments[0].scrollIntoView(true);", buy_button)
            time.sleep(1)
            buy_button.click()
            log_info("[SUCCESS] Кнопка 'Купить' нажата")
            time.sleep(2)
        except Exception as e:
            result["message"] = f"Ошибка при нажатии кнопки 'Купить': {e}"
            log_error(result["message"])
            return result

        # Проверка ошибок
        try:
            error_elems = driver.find_elements(By.CSS_SELECTOR, "div#msg-error")
            if error_elems:
                error_text = error_elems[0].text
                result["message"] = f"Ошибка: {error_text}"
                log_error(result["message"])
                return result
        except:
            pass
        
        # ✅ Успешное завершение
        log_info(f"[COMPLETE - PART 2] Пакеты для {client_username} успешно куплены!")
        result["ok"] = True
        result["message"] = f"Пакеты для {client_username} успешно куплены"
        
        # 📺 Загружаем IPTV информацию ДО закрытия браузера
        log_info("[STEP 6] Загрузка IPTV информации...")
        try:
            iptv_url = f"{base_url}/iptv_server.php?selected_user={client_username}"
            driver.get(iptv_url)
            time.sleep(3)
            
            html_content = driver.page_source
            result["iptv_html"] = html_content
            
            # Парсим ссылки через BeautifulSoup
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")
            
            def _clean_number(text: str) -> str:
                import re
                cleaned = re.sub(r"[^\d.,]", "", text or "")
                return cleaned.replace(" ", "")

            def _parse_int(text: str):
                try:
                    cleaned = _clean_number(text)
                    if not cleaned:
                        return None
                    return int(float(cleaned.replace(",", ".")))
                except Exception:
                    return None

            def _parse_decimal(text: str):
                from decimal import Decimal
                try:
                    cleaned = _clean_number(text)
                    if not cleaned:
                        return None
                    return Decimal(cleaned.replace(",", "."))
                except Exception:
                    return None

            # Ищем все ссылки
            all_links = [a.get("href") for a in soup.find_all("a") if a.get("href")]

            # Токен: сначала в скриптах, затем в параметрах ссылок
            import re
            token = None
            script_text = " ".join(soup.find_all(string=re.compile("clientToken")))
            token_match = re.search(r"clientToken\s*=\s*[\"']([A-Za-z0-9]+)[\"']", script_text or "")
            if token_match:
                token = token_match.group(1)
            if not token:
                from urllib.parse import urlparse, parse_qs
                for href in all_links:
                    parsed = urlparse(href)
                    q_token = parse_qs(parsed.query).get("token", [None])[0]
                    if q_token:
                        token = q_token
                        break

            # Парсим каналы и ссылки
            total_channels = 1214
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

            result["iptv_data"] = {
                "standard_link": next((l for l in all_links if "get.php" in l or "username" in l), None),
                "short_link": next((l for l in all_links if "/s/" in l), None),
                "m3u8_link": next((l for l in all_links if "m3u8" in l), None),
                "m3u_link": next((l for l in all_links if "m3u" in l and "m3u8" not in l), None),
                "spark_link": next((l for l in all_links if "spark" in l.lower()), None),
                "token": token,
                "active_subscribers": stats.get("active_subscribers"),
                "activated_per_day": stats.get("activated_per_day"),
                "activated_per_week": stats.get("activated_per_week"),
                "unused_funds": stats.get("unused_funds"),
                "total_channels": total_channels,
            }
            
            log_info(f"[SUCCESS] IPTV информация загружена: {sum(1 for v in result['iptv_data'].values() if v)} ссылок")
        except Exception as e:
            log_warning(f"[WARNING] Не удалось загрузить IPTV информацию: {e}")
            result["iptv_data"] = {}

    except Exception as e:
        result["message"] = f"Ошибка: {str(e)}"
        log_error(result["message"])
    finally:
        if driver:
            try:
                driver.quit()
                log_info("[CLEANUP] Браузер закрыт")
            except Exception as e:
                log_debug(f"[CLEANUP] Не удалось закрыть браузер: {e}")
            try:
                if hasattr(driver, "service") and driver.service:
                    driver.service.stop()
                    log_debug("[CLEANUP] Сервис вебдрайвера остановлен")
            except Exception as e:
                log_debug(f"[CLEANUP] Не удалось остановить сервис драйвера: {e}")
            driver = None

    return result


def add_client_to_dealer(client_username: str, client_password: str, subscription: str) -> dict:
    """
    [DEPRECATED] Старая функция - добавляла клиента И покупала пакеты в одном процессе.
    Теперь используйте:
    - auto_add_client_only() для добавления клиента
    - auto_buy_packages() для покупки пакетов

    Оставляю для обратной совместимости.

    Args:
        client_username: Логин клиента
        client_password: Пароль клиента
        subscription: Название пакета или комментарий

    Returns:
        dict: {"ok": bool, "message": str}
    """
    # Настройка браузера
    driver = None
    result = {"ok": False, "message": ""}

    try:
        driver = _build_driver(headless=True)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_info(f"[START] Начинаем добавление клиента: {client_username}")

        # 1) Вход как дилер
        log_info("[STEP 1] Авторизация на сайте дилера")
        base_url = _get_dealer_url()
        if not base_url:
            result["message"] = "DEALER_URL не настроен"
            log_error(result["message"])
            return result
        driver.get(base_url)
        
        WebDriverWait(driver, SHORT_TIMEOUT).until(
            EC.presence_of_element_located((By.NAME, "field_login"))
        )
        
        driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
        driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
        driver.find_element(By.NAME, "submit_login").click()
        
        time.sleep(2)
        log_info("[SUCCESS] Авторизация выполнена")

        # 2) Переход к форме добавления клиента
        log_info("[STEP 2] Переход к форме добавления клиента")
        if not wait_and_click(driver, By.CSS_SELECTOR, "a[href='/add_client.php']", SHORT_TIMEOUT, "add_client.php"):
            if not wait_and_click(driver, By.XPATH, "//a[contains(@href, 'add_client.php')]", SHORT_TIMEOUT, "add_client.php (XPATH)"):
                result["message"] = "Не найдена ссылка на страницу добавления клиента"
                log_error(result["message"])
                return result

        time.sleep(1)

        # 3) Заполнение данных клиента
        log_info("[STEP 3] Заполнение формы клиента")
        try:
            WebDriverWait(driver, SHORT_TIMEOUT).until(
                EC.presence_of_element_located((By.NAME, "login"))
            )
            
            driver.find_element(By.NAME, "login").send_keys(client_username)
            driver.find_element(By.NAME, "password_new").send_keys(client_password)
            driver.find_element(By.NAME, "password_confirm").send_keys(client_password)
            driver.find_element(By.NAME, "notice").send_keys(subscription)
            
            log_info("[SUCCESS] Форма заполнена")
            
        except NoSuchElementException as e:
            result["message"] = f"Не найдены поля формы: {e}"
            log_error(result["message"])
            return result

        # 4) Сохранение клиента
        log_info("[STEP 4] Сохранение клиента")
        try:
            save_button = driver.find_element(By.NAME, "save")
            save_button.click()
            time.sleep(2)
            log_info("[SUCCESS] Клиент сохранён")
            
        except NoSuchElementException:
            result["message"] = "Не найдена кнопка сохранения"
            log_error(result["message"])
            return result

        # Проверка: существует ли клиент
        error_elems = driver.find_elements(By.CSS_SELECTOR, "div#msg-error, .error-message")
        if error_elems:
            error_text = error_elems[0].text
            result["message"] = f"Клиент уже существует или ошибка: {error_text}"
            log_error(result["message"])
            return result

        # 5) Переход на страницу dealer.php
        log_info("[STEP 5] Переход в панель дилера")
        if not wait_and_click(driver, By.XPATH, "//a[contains(@href, 'dealer.php')]", DEFAULT_TIMEOUT, "dealer.php"):
            result["message"] = "Не найдена ссылка на панель дилера"
            log_error(result["message"])
            return result
        
        time.sleep(2)
        log_info("[SUCCESS] Панель дилера открыта")

        # 6) Переход на страницу пакетов
        packets_link = f"/packets.php?selected_user={client_username}"
        log_info(f"[STEP 6] Переход к покупке пакетов: {packets_link}")
        
        if not wait_and_click(driver, By.XPATH, f"//a[contains(@href, '{packets_link}')]", DEFAULT_TIMEOUT, "packets.php"):
            result["message"] = "Не найдена ссылка на страницу пакетов"
            log_error(result["message"])
            return result
        
        time.sleep(2)
        log_info("[SUCCESS] Страница пакетов загружена")

        # 7) Выбираем чекбокс пакета
        log_info("[STEP 7] Выбор пакета")
        
        package_selectors = [
            "//input[@name='user_packet_groups[]' and contains(@value, 'Акционный')]",
            "//input[@name='user_packet_groups[]'][1]",
            "//input[@type='checkbox'][1]",
            "input[name='user_packet_groups[]']"
        ]
        
        package_selected = False
        for selector in package_selectors:
            by_type = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            if wait_and_click(driver, by_type, selector, SHORT_TIMEOUT, "пакета"):
                package_selected = True
                break
        
        if not package_selected:
            result["message"] = "Не удалось выбрать пакет"
            log_error(result["message"])
            return result

        # 8) Выбираем срок подписки (365 дн.)
        log_info("[STEP 8] Выбор срока подписки")
        try:
            period_element = driver.find_element(By.XPATH, "//a[contains(text(),'365 дн.')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", period_element)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", period_element)
            log_info("[SUCCESS] Срок подписки выбран")
        except Exception as e:
            log_info(f"[WARNING] Не удалось выбрать срок: {e}")

        # 9) Нажимаем кнопку "Купить"
        log_info("[STEP 9] Оформление покупки")
        if not wait_and_click(driver, By.CSS_SELECTOR, "input[name='submit'][value='Купить']", SHORT_TIMEOUT, "Купить"):
            if not wait_and_click(driver, By.XPATH, "//input[@type='submit' and contains(@value, 'Купить')]", SHORT_TIMEOUT, "Купить (XPATH)"):
                result["message"] = "Не удалось нажать кнопку 'Купить'"
                log_error(result["message"])
                return result

        time.sleep(2)

        # Проверка: есть ли сообщение об ошибке
        error_elems = driver.find_elements(By.CSS_SELECTOR, "div#msg-error, .error-message")
        if error_elems:
            error_text = error_elems[0].text
            result["message"] = f"Ошибка при покупке: {error_text}"
            log_error(result["message"])
            return result
        
        # Успешное завершение
        log_info("[COMPLETE] Клиент добавлен и подписка оформлена успешно!")
        result["ok"] = True
        result["message"] = "Клиент добавлен и подписка оформлена"

    except TimeoutException as e:
        result["message"] = f"Превышено время ожидания: {str(e)}"
        log_error(result["message"])
    except WebDriverException as e:
        result["message"] = f"Ошибка WebDriver: {str(e)}"
        log_error(result["message"])
    except Exception as e:
        result["message"] = f"Непредвиденная ошибка: {str(e)}"
        log_error(result["message"])
    finally:
        if driver:
            try:
                driver.quit()
                log_info("[CLEANUP] Браузер закрыт")
            except:
                pass

    return result
