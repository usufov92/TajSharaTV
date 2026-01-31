import logging
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from django.conf import settings
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Константы
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
SHORT_TIMEOUT = 10
PAGE_LOAD_TIMEOUT = 60

# Используем именованный логгер, чтобы маршрутизировать через Django dictConfig
logger = logging.getLogger("automation")


def _build_driver(headless: bool = True):
    """Создаёт Chrome WebDriver с преднастроенными опциями."""
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    chromedriver_path = getattr(settings, 'CHROMEDRIVER_PATH', None)
    import os
    if chromedriver_path and os.path.exists(chromedriver_path):
        service = Service(chromedriver_path)
    else:
        service = Service(ChromeDriverManager().install())
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
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = None
    result = {"ok": False, "data": {}, "html": "", "message": ""}

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(120)
        
        log_debug(f"[DEBUG] Получаем IPTV информацию для: {client_username}")

        base_url = settings.DEALER_URL.rstrip("/")
        
        # Авторизация
        try:
            driver.get(base_url)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "field_login")))
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
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = None
    result = {"ok": False, "packages": [], "html": "", "message": ""}

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_debug(f"[DEBUG] Получаем информацию о пакетах для: {client_username}")

        base_url = settings.DEALER_URL.rstrip("/")
        
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
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    driver = None
    result = {"ok": False, "message": ""}

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_info(f"[PART 1] Начинаем добавление клиента: {client_username}")

        # Шаг 1: Авторизация на сайте дилера
        log_info("[STEP 1] Авторизация на сайте дилера")
        driver.get(settings.DEALER_URL)
        
        WebDriverWait(driver, SHORT_TIMEOUT).until(
            EC.presence_of_element_located((By.NAME, "field_login"))
        )
        
        driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
        driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
        driver.find_element(By.NAME, "submit_login").click()
        
        time.sleep(2)
        log_info("[SUCCESS] Авторизация выполнена")

        # Шаг 2: Переход к форме добавления клиента
        log_info("[STEP 2] Переход к форме добавления клиента")
        if not wait_and_click(driver, By.CSS_SELECTOR, "a[href='/add_client.php']", SHORT_TIMEOUT, "add_client.php"):
            if not wait_and_click(driver, By.XPATH, "//a[contains(@href, 'add_client.php')]", SHORT_TIMEOUT, "add_client.php (XPATH)"):
                result["message"] = "Не найдена ссылка на страницу добавления клиента"
                log_error(result["message"])
                return result

        time.sleep(1)

        # Шаг 3: Заполнение данных клиента
        log_info("[STEP 3] Заполнение формы клиента")
        try:
            WebDriverWait(driver, SHORT_TIMEOUT).until(
                EC.presence_of_element_located((By.NAME, "login"))
            )
            
            driver.find_element(By.NAME, "login").send_keys(client_username)
            driver.find_element(By.NAME, "password_new").send_keys(client_password)
            driver.find_element(By.NAME, "password_confirm").send_keys(client_password)
            if subscription:
                driver.find_element(By.NAME, "notice").send_keys(subscription)
            
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
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = None
    packages = []

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_debug(f"[DEBUG] Получаем доступные пакеты для: {client_username}")

        base_url = settings.DEALER_URL.rstrip("/")
        
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
        driver = _build_driver(headless=True)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

        log_info(f"[CHECK] Проверяем клиента {client_username} на сайте дилера")

        # Авторизация
        try:
            driver.get(settings.DEALER_URL)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "field_login")))
            driver.find_element(By.NAME, "field_login").send_keys(settings.DEALER_LOGIN)
            driver.find_element(By.NAME, "field_password").send_keys(settings.DEALER_PASSWORD)
            driver.find_element(By.NAME, "submit_login").click()
            time.sleep(2)
        except Exception as e:
            result["message"] = f"Ошибка авторизации дилера: {e}"
            log_error(result["message"])
            return result

        # Открываем страницу пакетов конкретного клиента
        packets_url = f"{settings.DEALER_URL}/packets.php?selected_user={client_username}"
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


def auto_buy_packages(client_username: str, package_names: list = None, days: int = 360) -> dict:
    """
    💰 ЧАСТЬ 2: Покупка пакетов для клиента на сайте дилера.
    
    Шаги:
    1. Авторизуется как дилер
    2. Переходит прямо на страницу пакетов по URL
    3. Выбирает чекбокс пакета
    4. Выбирает срок подписки
    5. Нажимает "Купить"
    6. Закрывает браузер
    
    Args:
        client_username: Логин клиента
        package_names: Список названий пакетов для выбора (по value атрибуту)
        days: Количество дней для подписки (по умолчанию 360)
    
    Returns:
        dict: {"ok": bool, "message": str}
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = None
    result = {"ok": False, "message": ""}

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_info(f"[PART 2] Начинаем покупку пакетов для клиента: {client_username}")

        # Шаг 1: Авторизация на сайте дилера
        log_info("[STEP 1] Загрузка страницы авторизации")
        log_info(f"[DEBUG] URL: {settings.DEALER_URL}")
        try:
            driver.get(settings.DEALER_URL)
            log_info("[DEBUG] GET запрос отправлен, ждём элемент field_login...")
        except Exception as e:
            log_error(f"[ERROR] Ошибка при загрузке URL: {e}")
            result["message"] = f"Ошибка загрузки: {e}"
            return result
        
        # Явное ожидание формы авторизации
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.NAME, "field_login"))
            )
            log_info("[SUCCESS] Страница авторизации загружена")
        except TimeoutException:
            log_error("[ERROR] Таймаут ожидания формы авторизации")
            result["message"] = "Форма авторизации не загрузилась"
            return result
        
        # Заполняем форму входа
        log_info("[STEP 2] Вход в аккаунт")
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

        # Шаг 2: Переход прямо на страницу пакетов (без промежуточных кликов)
        log_info(f"[STEP 3] Переход на пакеты клиента {client_username}")
        packets_url = f"{settings.DEALER_URL}/packets.php?selected_user={client_username}"
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
            checkbox.click()
            log_info("[SUCCESS] Чекбокс пакета выбран")
            time.sleep(2)
            
        except Exception as e:
            result["message"] = f"Ошибка при выборе пакета: {e}"
            log_error(result["message"])
            return result

        # Шаг 4: Выбор срока подписки
        log_info(f"[STEP 4] Выбор срока подписки: {days} дн.")
        try:
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
            driver.find_element(By.CSS_SELECTOR, "input[name='submit'][value='Купить']").click()
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
            iptv_url = f"{settings.DEALER_URL}/iptv_server.php?selected_user={client_username}"
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
    options = Options()
    options.add_argument("--headless")  # фоновый режим
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    driver = None
    result = {"ok": False, "message": ""}

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        log_info(f"[START] Начинаем добавление клиента: {client_username}")

        # 1) Вход как дилер
        log_info("[STEP 1] Авторизация на сайте дилера")
        driver.get(settings.DEALER_URL)
        
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

        # 8) Выбираем срок подписки (360 дн.)
        log_info("[STEP 8] Выбор срока подписки")
        try:
            period_element = driver.find_element(By.XPATH, "//a[contains(text(),'360 дн.')]")
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
