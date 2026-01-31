def notify_topup_request(manager_username: str, amount_usd: float, amount_tjs: float, request_id: int, transaction_proof: str = '', admin_id: int = None) -> bool:
    """
    📝 Уведомление админу о новой заявке на пополнение баланса
    Args:
        manager_username: логин менеджера
        amount_usd: сумма в USD
        amount_tjs: сумма в TJS
        request_id: номер заявки
        transaction_proof: подтверждение перевода (номер транзакции)
        admin_id: Telegram ID админа (по умолчанию settings.TELEGRAM_ADMIN_ID)
    Returns:
        bool: успех отправки
    """
    logger.info(f"[DEBUG] notify_topup_request called with: manager_username={manager_username}, amount_usd={amount_usd}, amount_tjs={amount_tjs}, request_id={request_id}, transaction_proof={transaction_proof}, admin_id={admin_id}")
    if not admin_id:
        admin_id = getattr(settings, 'TELEGRAM_ADMIN_ID', None)
    if not admin_id:
        logger.warning("[DEBUG] notify_topup_request: TELEGRAM_ADMIN_ID not set, notification not sent.")
        return False
    SITE_NAME = getattr(settings, 'SITE_NAME', 'DealerSync')
    message = (
        f"🌐 <b>{SITE_NAME}</b>\n"
        f"📝 <b>Заявка на пополнение</b>\n\n"
        f"#️⃣ Заявка: <b>#{request_id}</b>\n"
        f"👤 Mgr: <b>{manager_username}</b>\n"
        f"💵 Сумма: <b>{amount_tjs:.2f} TJS</b> (≈ <b>${amount_usd:.2f}</b>)\n"
        f"🔖 Номер чек: <b>{transaction_proof}</b>\n\n"
        f"Пожалуйста, одобрите заявку."
    )
    logger.info(f"[DEBUG] notify_topup_request: Sending message to admin_id={admin_id}: {message}")
    return send_telegram_message(admin_id, message)
def notify_topup_balance(manager_username: str, amount: float, old_balance: float, new_balance: float, admin_id: int = None) -> bool:
    """
    💸 Уведомление о пополнении баланса менеджера (только админу)
    Args:
        manager_username: логин менеджера
        amount: сумма пополнения
        old_balance: баланс до
        new_balance: баланс после
        admin_id: Telegram ID админа (по умолчанию settings.TELEGRAM_ADMIN_ID)
    Returns:
        bool: успех отправки
    """
    if not admin_id:
        admin_id = getattr(settings, 'TELEGRAM_ADMIN_ID', None)
    if not admin_id:
        return False
    SITE_NAME = getattr(settings, 'SITE_NAME', 'DealerSync')
    message = (
        f"🌐 <b>{SITE_NAME}</b>\n"
        f"💸 <b>Пополнение баланса менеджера</b>\n\n"
        f"👤 Менеджер: <b>{manager_username}</b>\n"
        f"➕ Сумма: <b>${amount:.2f}</b>\n"
        f"💰 Было: <b>${old_balance:.2f}</b> → Стало: <b>${new_balance:.2f}</b>\n\n"
        f"<i>{get_formatted_time()}</i>"
    )
    return send_telegram_message(admin_id, message)
"""
📱 Telegram уведомления для менеджеров
"""
import logging
import asyncio
from django.conf import settings
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


def send_telegram_message(chat_id: int, message: str, parse_mode: str = "HTML") -> bool:
    """
    Отправить сообщение в Telegram
    
    Args:
        chat_id: ID чата (user_id или admin_id)
        message: Текст сообщения (поддерживает HTML разметку)
        parse_mode: 'HTML' или 'Markdown'
    
    Returns:
        bool: True если отправлено успешно
    """
    try:
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not bot_token:
            logger.warning("[Telegram] TELEGRAM_BOT_TOKEN не установлен в settings")
            return False
        
        # Используем asyncio для отправки сообщения
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            _send_async(bot_token, chat_id, message, parse_mode)
        )
        loop.close()
        return result
    except Exception as e:
        logger.error(f"[Telegram] Ошибка при отправке сообщения: {e}")
        return False


async def _send_async(bot_token: str, chat_id: int, message: str, parse_mode: str) -> bool:
    """Асинхронная отправка сообщения"""
    try:
        bot = Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=message, parse_mode=parse_mode)
        logger.info(f"[Telegram] Сообщение отправлено пользователю {chat_id}")
        return True
    except TelegramError as e:
        logger.error(f"[Telegram] API ошибка: {e}")
        return False
    except Exception as e:
        logger.error(f"[Telegram] Ошибка: {e}")
        return False


def notify_purchase(username: str, subscription: str, cost: float, manager_id: int = None) -> bool:
    """
    📦 Уведомление о покупке пакетов
    
    Args:
        username: Логин клиента
        subscription: Название пакета
        cost: Стоимость
        manager_id: ID менеджера в Telegram (опционально)
    
    Returns:
        bool: Успех отправки
    """
    if not manager_id:
        manager_id = getattr(settings, 'TELEGRAM_ADMIN_ID', None)
    
    if not manager_id:
        logger.warning("[Telegram] TELEGRAM_ADMIN_ID не установлен")
        return False
    
    SITE_NAME = getattr(settings, 'SITE_NAME', 'DealerSync')
    message = (
        f"🌐 <b>{SITE_NAME}</b>\n"
        f"✅ <b>Успешная покупка пакетов</b>\n\n"
        f"👤 Клиент: <code>{username}</code>\n"
        f"📦 Пакет: <b>{subscription}</b>\n"
        f"💰 Стоимость: <b>${cost:.2f}</b>\n\n"
        f"<i>Время: {get_formatted_time()}</i>"
    )
    return send_telegram_message(manager_id, message)


def notify_expiry_warning(username: str, subscription: str, end_date: str, manager_id: int = None) -> bool:
    """
    ⏳ Уведомление об истечении подписки (за 1 день)
    
    Args:
        username: Логин клиента
        subscription: Название пакета
        end_date: Дата окончания (строка)
        manager_id: ID менеджера в Telegram
    
    Returns:
        bool: Успех отправки
    """
    if not manager_id:
        manager_id = getattr(settings, 'TELEGRAM_ADMIN_ID', None)
    
    if not manager_id:
        return False
    
    SITE_NAME = getattr(settings, 'SITE_NAME', 'DealerSync')
    message = (
        f"🌐 <b>{SITE_NAME}</b>\n"
        f"⏳ <b>Подписка истекает завтра</b>\n\n"
        f"👤 Клиент: <code>{username}</code>\n"
        f"📦 Пакет: <b>{subscription}</b>\n"
        f"📅 Конец подписки: <b>{end_date}</b>\n\n"
        f"<i>Требуется продление</i>"
    )
    return send_telegram_message(manager_id, message)


def notify_balance_low(manager_name: str, balance: float, manager_id: int = None) -> bool:
    """
    💳 Уведомление о низком балансе
    
    Args:
        manager_name: Имя менеджера
        balance: Текущий баланс
        manager_id: ID менеджера в Telegram
    
    Returns:
        bool: Успех отправки
    """
    if not manager_id:
        manager_id = getattr(settings, 'TELEGRAM_ADMIN_ID', None)
    
    if not manager_id:
        return False
    
    SITE_NAME = getattr(settings, 'SITE_NAME', 'DealerSync')
    message = (
        f"🌐 <b>{SITE_NAME}</b>\n"
        f"💳 <b>Низкий баланс</b>\n\n"
        f"👤 Менеджер: <b>{manager_name}</b>\n"
        f"💰 Баланс: <b>${balance:.2f}</b>\n\n"
        f"<i>Пополните баланс через admin панель</i>"
    )
    return send_telegram_message(manager_id, message)


def notify_error(error_title: str, error_msg: str, manager_id: int = None) -> bool:
    """
    ❌ Уведомление об ошибке
    
    Args:
        error_title: Название ошибки
        error_msg: Описание
        manager_id: ID менеджера в Telegram
    
    Returns:
        bool: Успех отправки
    """
    if not manager_id:
        manager_id = getattr(settings, 'TELEGRAM_ADMIN_ID', None)
    
    if not manager_id:
        return False
    
    SITE_NAME = getattr(settings, 'SITE_NAME', 'DealerSync')
    message = (
        f"🌐 <b>{SITE_NAME}</b>\n"
        f"❌ <b>{error_title}</b>\n\n"
        f"<code>{error_msg}</code>\n\n"
        f"<i>{get_formatted_time()}</i>"
    )
    return send_telegram_message(manager_id, message)


def get_formatted_time() -> str:
    """Получить текущее время в формате"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
