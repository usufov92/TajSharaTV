# 📱 Настройка SmsMobile API

## Что добавлено

Добавлена полная поддержка **SmsMobile API** для отправки SMS-уведомлений.

---

## Настройка API ключей

### Шаг 1: Получите доступ к SmsMobile

1. Зарегистрируйтесь на **https://smsmobile.ru**
2. Пополните баланс (минимум 100-300 рублей для теста)
3. Получите логин и пароль API в личном кабинете

### Шаг 2: Настройте .env файл

Откройте `.env` и замените:

```env
# SMS настройки (SmsMobile API)
SMS_PROVIDER=smsmobile
SMS_API_URL=https://smsmobileapi.com/lcabApi/sendSms.php
SMS_API_KEY=ваш_логин
SMS_API_PASSWORD=ваш_пароль
SMS_SENDER=TajSharaTV 
```

**Параметры:**
- `SMS_API_KEY` — ваш логин в SmsMobile
- `SMS_API_PASSWORD` — ваш пароль
- `SMS_SENDER` — имя отправителя (до 11 символов латиницей)

---

## Тарифы SmsMobile

### Для Таджикистана:
- **1 SMS ≈ 2-3 рубля** (~0.02-0.03 USD)
- Минимальное пополнение: **100 рублей**
- Доставка: **1-5 секунд**

### Поддерживаемые операторы:
- ✅ Tcell
- ✅ Megafon TJ
- ✅ Beeline TJ
- ✅ Zet-Mobile

---

## Тестирование

### 1. Проверка подключения

```cmd
python manage.py send_expiry_notifications --force-phone +992XXXXXXXXX
```

Если всё настроено правильно, вы получите SMS на указанный номер.

### 2. Тестовый режим (без отправки)

```cmd
python manage.py send_expiry_notifications --dry-run
```

Покажет список клиентов без реальной отправки.

---

## Формат ответа SmsMobile

### Успешная отправка:
```
0
```
или
```json
{"status": "ok", "code": 0, "message_id": "12345"}
```

### Ошибки:

| Код | Описание |
|-----|----------|
| -1  | Неверный логин/пароль |
| -2  | Недостаточно средств |
| -3  | Неверный формат номера |
| -4  | Текст сообщения пустой |
| -5  | Недопустимый отправитель |

---

## Мониторинг отправок

### 1. Через админку Django

Админка → **SMS логи** — все отправки с результатами

### 2. Через файл логов

```cmd
type logs\sms_notifications.log
```

### 3. В личном кабинете SmsMobile

https://smsmobile.ru — статистика и история

---

## Автозапуск

После настройки API запустите Task Scheduler:

```cmd
send_sms_daily.bat
```

Или следуйте инструкциям в [SMS_SETUP_GUIDE.md](SMS_SETUP_GUIDE.md)

---

## Частые проблемы

### Ошибка "-1: Неверный логин/пароль"
- Проверьте `SMS_API_KEY` и `SMS_API_PASSWORD` в `.env`
- Убедитесь, что нет лишних пробелов

### Ошибка "-2: Недостаточно средств"
- Пополните баланс в личном кабинете SmsMobile

### Ошибка "-3: Неверный формат номера"
- Номер должен быть: `+992XXXXXXXXX`
- Проверьте номера клиентов в базе

### SMS не приходит, но API возвращает "0"
- Проверьте имя отправителя `SMS_SENDER`
- Некоторые имена требуют регистрации

---

## Стоимость

При **50 клиентах** с истекающими подписками ежедневно:
- **50 SMS × 2.5₽ = 125₽/день**
- **≈ 3750₽/месяц** (~40 USD)

Для экономии:
- Уменьшите частоту уведомлений (только за 1 день)
- Используйте комбинацию SMS + Telegram Bot

---

## Поддержка SmsMobile

- **Email:** support@smsmobile.ru
- **Телефон:** +7 (495) 505-71-50
- **Telegram:** @smsmobile_support
- **Документация:** https://smsmobile.ru/api/

---

## Для клона IPTV

Скопируйте настройки в `dealer-sync-iptv/.env`:

```env
SMS_PROVIDER=smsmobile
SMS_API_URL=https://smsmobileapi.com/lcabApi/sendSms.php
SMS_API_KEY=ваш_логин
SMS_API_PASSWORD=ваш_пароль
SMS_SENDER=TajSharaTV
```
