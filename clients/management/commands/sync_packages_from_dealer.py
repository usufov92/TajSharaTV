"""
Django команда для синхронизации пакетов с сайта дилера
Использование: python manage.py sync_packages_from_dealer [username]
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from clients.models import Package
from clients.automation import _build_driver, _get_dealer_url, log_info, log_error
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import re


class Command(BaseCommand):
    help = 'Синхронизирует пакеты с сайта дилера в БД'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='demo',
            help='Логин клиента для загрузки страницы пакетов (по умолчанию: demo)'
        )

    def handle(self, *args, **options):
        username = options['username']
        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(f"🔄 Синхронизация пакетов с сайта дилера")
        self.stdout.write(f"{'='*80}\n")
        
        result = self.sync_packages_from_dealer(username)
        
        if result['ok']:
            self.stdout.write(self.style.SUCCESS(f"\n✅ {result['message']}"))
            self.stdout.write(f"\n📊 Статистика:")
            self.stdout.write(f"   ✅ Создано:   {result['created']}")
            self.stdout.write(f"   🔄 Обновлено: {result['updated']}")
            self.stdout.write(f"   📦 Всего в БД: {Package.objects.count()}")
        else:
            self.stdout.write(self.style.ERROR(f"\n❌ {result['message']}"))
        
        self.stdout.write(f"\n{'='*80}\n")

    def sync_packages_from_dealer(self, client_username: str) -> dict:
        """
        Загружает пакеты с сайта дилера и сохраняет в БД
        Использует requests вместо Selenium для быстроты
        
        Args:
            client_username: Логин клиента для загрузки страницы пакетов
            
        Returns:
            dict: {
                "ok": bool,
                "message": str,
                "created": int,
                "updated": int,
                "packages": list
            }
        """
        import requests
        from urllib.parse import urlparse, parse_qs
        
        result = {
            "ok": False,
            "message": "",
            "created": 0,
            "updated": 0,
            "packages": []
        }

        try:
            log_info(f"[SYNC] Начинаем синхронизацию пакетов для клиента: {client_username}")

            # Создаем сессию
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            # Шаг 1: Получаем base URL
            base_url = _get_dealer_url()
            if not base_url:
                result["message"] = "DEALER_URL не настроен"
                log_error(result["message"])
                return result
            
            log_info("[STEP 1] Авторизация на сайте дилера")
            
            # Делаем первый GET запрос для получения cookies
            try:
                response = session.get(base_url, timeout=10, allow_redirects=True)
                
                # Извлекаем ssn из редиректа если есть
                parsed_url = urlparse(response.url)
                query_params = parse_qs(parsed_url.query)
                ssn = query_params.get('ssn', [None])[0]
                
                log_info(f"ssn: {ssn}")
                
            except Exception as e:
                result["message"] = f"Ошибка GET запроса: {e}"
                log_error(result["message"])
                return result
            
            # Шаг 2: Авторизация
            login_url = f"{base_url}/login.php"
            if ssn:
                login_url += f"?ssn={ssn}"
            
            login_data = {
                'field_login': settings.DEALER_LOGIN,
                'field_password': settings.DEALER_PASSWORD,
                'submit_login': 'Войти'
            }
            
            try:
                response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)
                
                # Проверяем успешность авторизации
                if 'login.php' in response.url.lower():
                    result["message"] = "Ошибка авторизации: не удалось войти"
                    log_error(result["message"])
                    return result
                
                log_info("[SUCCESS] Авторизация выполнена")
                
            except Exception as e:
                result["message"] = f"Ошибка POST запроса: {e}"
                log_error(result["message"])
                return result

            # Шаг 3: Загрузка страницы пакетов
            log_info(f"[STEP 2] Загрузка страницы пакетов для {client_username}")
            
            packets_url = f"{base_url}/packets.php?selected_user={client_username}"
            if ssn:
                packets_url += f"&ssn={ssn}"
            
            try:
                response = session.get(packets_url, timeout=10)
                html_content = response.text
                
                log_info(f"[SUCCESS] Страница загружена, размер: {len(html_content)} байт")
                
            except Exception as e:
                result["message"] = f"Ошибка загрузки страницы пакетов: {e}"
                log_error(result["message"])
                return result
            
            # Шаг 4: Парсинг HTML
            log_info("[STEP 3] Парсинг HTML страницы")
            
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Находим все скрипты с ценами пакетов
            # packet_group_prices["Акционный !! AlemTV"] = 0.001667;
            price_pattern = re.compile(r'packet_group_prices\["([^"]+)"\]\s*=\s*([\d.]+);')
            
            packages_data = {}
            for script in soup.find_all("script"):
                if script.string:
                    for match in price_pattern.finditer(script.string):
                        name = match.group(1)
                        price_per_day = float(match.group(2))
                        price_per_month = round(price_per_day * 30, 2)
                        packages_data[name] = price_per_month
            
            log_info(f"[SUCCESS] Найдено {len(packages_data)} пакетов в скриптах")
            
            if not packages_data:
                result["message"] = "Пакеты не найдены на странице"
                log_error(result["message"])
                return result
            
            # Шаг 5: Сохранение в БД
            log_info("[STEP 4] Сохранение пакетов в БД")
            
            for name, price in packages_data.items():
                try:
                    # Проверяем что это акционный пакет
                    is_promo = name.startswith('Акционный !!')
                    
                    # Получаем или создаём пакет
                    package, created = Package.objects.get_or_create(
                        name=name,
                        defaults={
                            'price': price,
                            'is_promo': is_promo,
                        }
                    )
                    
                    if created:
                        result["created"] += 1
                        status = "✅ СОЗДАН"
                        log_info(f"{status}: {name} | ${price}")
                    else:
                        # Обновляем цену если изменилась
                        if float(package.price) != price:
                            package.price = price
                            package.is_promo = is_promo
                            package.save()
                            result["updated"] += 1
                            status = "🔄 ОБНОВЛЁН"
                            log_info(f"{status}: {name} | ${price}")
                        else:
                            status = "ℹ️ СУЩЕСТВУЕТ"
                    
                    result["packages"].append({
                        "name": name,
                        "price": price,
                        "is_promo": is_promo,
                        "status": status
                    })
                    
                except Exception as e:
                    log_error(f"❌ ОШИБКА при сохранении {name}: {e}")
                    continue
            
            result["ok"] = True
            result["message"] = f"Синхронизация завершена: {result['created']} создано, {result['updated']} обновлено"
            log_info(f"[COMPLETE] {result['message']}")

        except Exception as e:
            result["message"] = f"Ошибка синхронизации: {str(e)}"
            log_error(result["message"])

        return result
