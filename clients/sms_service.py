# Универсальная функция для параллельных уведомлений через SMS и WhatsApp
def send_notification(
    phone: str,
    message: str = None,
    whatsapp: bool = None,
    sms: bool = None,
    username: str = None,
    manager: str = None
) -> dict:
    """
    Отправляет уведомление: если у номера есть WhatsApp — только WhatsApp, иначе только SMS.
    Управляется переменными .env: NOTIFY_USE_SMS, NOTIFY_USE_WHATSAPP, NOTIFY_TEMPLATE_EXPIRY, NOTIFY_TEMPLATE_WHATSAPP.
    """
    if sms is None:
        sms = os.getenv('NOTIFY_USE_SMS', 'True').lower() == 'true'
    if whatsapp is None:
        whatsapp = os.getenv('NOTIFY_USE_WHATSAPP', 'True').lower() == 'true'

    # Шаблоны сообщений
    if not message:
        template = os.getenv('NOTIFY_TEMPLATE_EXPIRY', 'Уважаемый {username}, напоминаем: через 3 дня истекает срок оплаты IPTV. {manager}')
        manager_text = f'Для продления позвоните менеджеру {manager}.' if manager else 'Для продления свяжитесь с вашим менеджером.'
        message = template.format(username=username or '', manager=manager_text)
    wa_template = os.getenv('NOTIFY_TEMPLATE_WHATSAPP', 'Здравствуйте, {username}! Ваш IPTV заканчивается через 3 дня. {manager}')
    wa_manager_text = f'Обратитесь к менеджеру {manager}.' if manager else 'Свяжитесь с вашим менеджером.'
    wa_message = wa_template.format(username=username or '', manager=wa_manager_text)

    results = {}
    # Проверка наличия WhatsApp через SmsMobile API (или по шаблону номера)
    if whatsapp and has_whatsapp(phone):
        results['whatsapp'] = send_whatsapp_via_smsmobile(phone, wa_message)
    elif sms:
        sms_service = SMSService()
        results['sms'] = sms_service.send_sms(phone, message)
    else:
        results['error'] = 'Нет доступных каналов для отправки уведомления.'
    return results

# Проверка наличия WhatsApp у номера через SmsMobile API (или по шаблону)
def has_whatsapp(phone: str) -> bool:
    """
    Проверяет, поддерживает ли номер WhatsApp через SmsMobile API.
    Реализация: быстрый запрос с channel=whatsapp и коротким тестовым сообщением (не отправляет реальное уведомление).
    Важно: уточните у SmsMobile, есть ли отдельный API для проверки, иначе используйте шаблон (например, все номера TJ поддерживают WhatsApp).
    """
    # Пример: всегда True для номеров +992 (Таджикистан) — доработайте под свой регион/провайдера
    if phone.startswith('+992'):
        return True
    # Альтернативно: сделать реальный запрос (может быть платным!)
    # api_url = os.getenv('SMS_API_URL', '')
    # api_key = os.getenv('SMS_API_KEY', '')
    # payload = {'recipients': phone, 'message': 'test', 'apikey': api_key, 'channel': 'whatsapp', 'test': 1}
    # try:
    #     response = requests.get(api_url, params=payload, timeout=10)
    #     return response.status_code == 200 and 'whatsapp' in response.text.lower()
    # except Exception:
    #     return False
    return False

# WhatsApp через SmsMobile API (тот же endpoint, но с другим шаблоном)
def send_whatsapp_via_smsmobile(phone: str, message: str) -> dict:
    """
    Отправка WhatsApp-сообщения через SmsMobile API (если поддерживается тарифом).
    Логирует подробный ответ от провайдера для диагностики.
    """
    api_url = os.getenv('SMS_API_URL', '')
    api_key = os.getenv('SMS_API_KEY', '')
    sender = os.getenv('SMS_SENDER', 'TajSharaTV')
    payload = {
        'recipients': phone,
        'message': message,
        'apikey': api_key,
        'channel': 'whatsapp'
    }
    try:
        response = requests.get(api_url, params=payload, timeout=15)
        logger.info(f"SmsMobile WhatsApp API response: status={response.status_code}, text={response.text}")
        if response.status_code == 200:
            return {'success': True, 'response': response.text}
        else:
            return {'success': False, 'message': f'Ошибка API: {response.status_code}', 'error': response.text}
    except Exception as e:
        logger.error(f"Ошибка отправки WhatsApp через SmsMobile: {e}")
        return {'success': False, 'error': str(e)}
"""
SMS Service для отправки уведомлений клиентам.
Поддерживает различные SMS-провайдеры через HTTP API.
"""
import os
import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SMSService:
    """Универсальный класс для отправки SMS через HTTP API"""
    
    def __init__(self):
        self.api_url = os.getenv('SMS_API_URL', '')
        self.api_key = os.getenv('SMS_API_KEY', '')
        self.sender = os.getenv('SMS_SENDER', 'TajSharaTV')
        
    def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        """
        Отправка SMS сообщения
        
        Args:
            phone: Номер телефона получателя (формат: +992XXXXXXXXX)
            message: Текст сообщения
            
        Returns:
            dict: Результат отправки с ключами 'success' и 'message'
        """
        if not self.api_url or not self.api_key:
            logger.error("SMS API не настроен. Проверьте .env файл")
            return {
                'success': False,
                'message': 'SMS API не настроен',
                'error': 'Missing API credentials'
            }
        
        # Очистка номера телефона
        clean_phone = self._clean_phone(phone)
        
        if not clean_phone:
            return {
                'success': False,
                'message': f'Некорректный номер телефона: {phone}',
                'error': 'Invalid phone number'
            }
        
        try:
            # Универсальный формат для большинства SMS API
            payload = {
                'api_key': self.api_key,
                'sender': self.sender,
                'phone': clean_phone,
                'message': message
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f"SMS успешно отправлено на {clean_phone}")
                return {
                    'success': True,
                    'message': 'SMS отправлено',
                    'phone': clean_phone,
                    'response': response.json() if response.text else {}
                }
            else:
                logger.error(f"Ошибка отправки SMS: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'message': f'Ошибка API: {response.status_code}',
                    'error': response.text
                }
                
        except requests.RequestException as e:
            logger.error(f"Ошибка соединения с SMS API: {str(e)}")
            return {
                'success': False,
                'message': 'Ошибка соединения с SMS сервисом',
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке SMS: {str(e)}")
            return {
                'success': False,
                'message': 'Внутренняя ошибка',
                'error': str(e)
            }
    
    def _clean_phone(self, phone: str) -> Optional[str]:
        """
        Очистка и валидация номера телефона
        
        Args:
            phone: Исходный номер
            
        Returns:
            str: Очищенный номер в формате +992XXXXXXXXX или None
        """
        if not phone:
            return None
        
        # Удаление всех символов кроме цифр и +
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        # Проверка формата для Таджикистана
        if cleaned.startswith('+992') and len(cleaned) == 13:
            return cleaned
        elif cleaned.startswith('992') and len(cleaned) == 12:
            return '+' + cleaned
        elif len(cleaned) == 9:  # Формат без кода страны
            return '+992' + cleaned
        
        logger.warning(f"Некорректный формат номера: {phone}")
        return None
    
    def send_expiry_notification(
        self,
        phone: str,
        client_name: str = '',
        manager_phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Отправка уведомления об истечении подписки с контактом менеджера
        
        Args:
            phone: Номер телефона клиента
            client_name: Имя клиента (опционально)
            manager_phone: Телефон менеджера для связи (опционально)
            
        Returns:
            dict: Результат отправки с ключом sent_message
        """
        base_text = "Напоминаем: через 3 дня истекает срок оплаты IPTV."
        message = base_text

        if client_name:
            # Персонализированное начало сообщения для клиента
            message = f"Уважаемый {client_name}, {base_text.lower()}"

        # Добавляем телефон менеджера, если он есть
        if manager_phone:
            cleaned_manager_phone = self._clean_phone(manager_phone) or manager_phone
            message = f"{message} Для продления позвоните менеджеру {cleaned_manager_phone}."
        else:
            message = f"{message} Для продления свяжитесь с вашим менеджером."

        result = self.send_sms(phone, message)
        result['sent_message'] = message
        return result


class NikitaSMSService(SMSService):
    """Специализированный класс для Nikita SMS API"""
    
    def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        """Отправка через Nikita SMS API"""
        clean_phone = self._clean_phone(phone)
        
        if not clean_phone:
            return {'success': False, 'message': 'Некорректный номер'}
        
        try:
            # Формат для Nikita (пример, уточните у провайдера)
            payload = {
                'login': self.api_key,
                'password': os.getenv('SMS_API_PASSWORD', ''),
                'sender': self.sender,
                'recipient': clean_phone,
                'text': message
            }
            
            response = requests.get(
                self.api_url,
                params=payload,
                timeout=10
            )
            
            if response.status_code == 200 and 'OK' in response.text:
                logger.info(f"SMS успешно отправлено через Nikita на {clean_phone}")
                return {
                    'success': True,
                    'message': 'SMS отправлено',
                    'phone': clean_phone
                }
            else:
                logger.error(f"Ошибка Nikita API: {response.text}")
                return {
                    'success': False,
                    'message': 'Ошибка отправки',
                    'error': response.text
                }
                
        except Exception as e:
            logger.error(f"Ошибка Nikita SMS: {str(e)}")
            return {
                'success': False,
                'message': 'Ошибка соединения',
                'error': str(e)
            }


# SmsMobile API (СНГ)
class SmsMobileSMSService(SMSService):
    """Специализированный класс для SmsMobile API"""
    
    def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        """Отправка через SmsMobile API (api.smsmobileapi.com)"""
        clean_phone = self._clean_phone(phone)
        
        if not clean_phone:
            return {'success': False, 'message': 'Некорректный номер'}
        
        try:
            # SmsMobile API формат для api.smsmobileapi.com (GET запрос)
            params = {
                'recipients': clean_phone,
                'message': message,
                'apikey': self.api_key
            }
            
            # Отправка GET запроса
            response = requests.get(
                self.api_url,
                params=params,
                timeout=15
            )
            
            # Проверка ответа SmsMobile
            if response.status_code == 200:
                response_text = response.text.strip()
                
                # Проверяем различные форматы успешного ответа
                if response_text == '0' or 'OK' in response_text.upper() or 'success' in response_text.lower():
                    logger.info(f"SMS успешно отправлено через SmsMobile на {clean_phone}")
                    return {
                        'success': True,
                        'message': 'SMS отправлено',
                        'phone': clean_phone,
                        'response': response_text
                    }
                
                # Попытка парсить JSON ответ
                try:
                    json_response = response.json()
                    if json_response.get('status') == 'ok' or json_response.get('code') == 0 or json_response.get('success'):
                        logger.info(f"SMS успешно отправлено через SmsMobile на {clean_phone}")
                        return {
                            'success': True,
                            'message': 'SMS отправлено',
                            'phone': clean_phone,
                            'response': json_response
                        }
                except:
                    pass
                
                # Если ответ не распознан как успех
                logger.error(f"Ошибка SmsMobile API: {response_text}")
                return {
                    'success': False,
                    'message': f'Ошибка API: {response_text}',
                    'error': response_text
                }
            else:
                logger.error(f"Ошибка HTTP {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'message': f'Ошибка HTTP {response.status_code}',
                    'error': response.text
                }
                
        except requests.RequestException as e:
            logger.error(f"Ошибка соединения SmsMobile: {str(e)}")
            return {
                'success': False,
                'message': 'Ошибка соединения с SMS сервисом',
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Ошибка SmsMobile SMS: {str(e)}")
            return {
                'success': False,
                'message': 'Внутренняя ошибка',
                'error': str(e)
            }


# Фабрика для выбора провайдера
def get_sms_service() -> SMSService:
    """
    Возвращает экземпляр SMS сервиса в зависимости от настроек
    
    Returns:
        SMSService: Экземпляр SMS сервиса
    """
    provider = os.getenv('SMS_PROVIDER', 'generic').lower()
    
    if provider == 'nikita':
        return NikitaSMSService()
    elif provider == 'smsmobile':
        return SmsMobileSMSService()
    else:
        return SMSService()
