# TajSharaTV — TajSharaTV & Taj-IPTV

Универсальная система управления IPTV-подписками для дилеров с автоматизацией (Selenium), Telegram-уведомлениями и безопасной работой в двух инстансах: **TajSharaTV** и **Taj-IPTV**.

---

## 1. Установка и запуск

### 1.1. Клонирование и зависимости
```sh
git clone <ваш-репозиторий>
cd dealer-sync
pip install -r requirements.txt
```

### 1.2. Переменные окружения
Создайте файлы `.env` и `.env.iptv` (см. пример ниже):
```
SECRET_KEY=...           # Django secret
DEBUG=False              # Только для продакшн False
ALLOWED_HOSTS=127.0.0.1,localhost
SITE_NAME=TajSharaTV     # или Taj-IPTV
CHROMEDRIVER_PATH=...    # путь к chromedriver
TELEGRAM_TOKEN=...       # токен бота
TELEGRAM_CHAT_ID=...     # id чата для уведомлений
... (остальные переменные)
```

### 1.3. Миграции и суперпользователь
```sh
run_migrations.bat
python manage.py createsuperuser
python create_iptv_superuser.py
```

### 1.4. Запуск
```sh
run_both.bat
# или по отдельности: run.bat / runip.bat
```

---

## 2. Основные возможности

- Автоматизация управления клиентами и пакетами через Selenium
- Telegram-уведомления о всех бизнес-событиях (с указанием инстанса)
- SMS-уведомления о продлении
- Гибкая система скидок для менеджеров
- Безопасное разграничение прав (админ/менеджер)
- Поддержка двух независимых инстансов (TajSharaTV, Taj-IPTV)
- Поддержка Windows Task Scheduler для автоматизации
- Логирование всех действий

---

## 3. Безопасность и эксплуатация

- Все секреты и ключи — только в .env/.env.iptv (НЕ хранить в коде)
- DEBUG=False для продакшн
- .gitignore защищает .env, логи, временные файлы
- Все действия пользователей логируются
- CSRF и custom error page для защиты

---

## 4. Поддержка и обновления

- Для обновления зависимостей: `pip install -r requirements.txt`
- Для обновления кода: `git pull`
- Для смены переменных — редактируйте .env/.env.iptv и перезапустите сервис

---

## 5. Контакты и поддержка

- Вопросы по эксплуатации: <ваш email/support>
- Техническая документация: см. TECHNICAL_SPECIFICATION.md
1. **TajSharaTV** (основной) - порт 8000, БД `db.sqlite3`
2. **Taj-IPTV** (второй) - порт 8001, БД `db_iptv.sqlite3`

Каждый инстанс имеет:
- Свою базу данных SQLite
- Свои логи (`logs/` и `logs_iptv/`)
- Свою конфигурацию (`.env` и `.env.iptv`)
- Независимую систему пользователей

---

## 📁 Структура проекта

```
dealer-sync/
├── clients/              # Главное Django приложение
│   ├── automation.py     # Selenium автоматизация
│   ├── models.py         # Client, Profile, Package, Transaction, IPTVInfo
│   ├── views.py          # Представления
│   └── packages.json     # Данные пакетов
├── core/                 # Настройки Django
│   ├── settings.py       # Настройки TajSharaTV
│   ├── settings_iptv.py  # Настройки Taj-IPTV
│   └── urls.py           # URL маршруты
├── templates/            # HTML шаблоны
├── logs/                 # Логи с временными метками
├── logs_iptv/            
├── db.sqlite3            # БД TajSharaTV
├── db_iptv.sqlite3       # БД Taj-IPTV
├── .env                  # Конфигурация TajSharaTV
├── .env.iptv             # Конфигурация Taj-IPTV
└── manage.py
```

---

## 🔧 Основные команды

### База данных
```cmd
# Миграции для обоих инстансов
run_migrations.bat

# Отдельно
python manage.py migrate
python manage.py migrate --settings=core.settings_iptv
```

### Суперпользователи
```cmd
# TajSharaTV
python manage.py createsuperuser

# Taj-IPTV
python create_iptv_superuser.py
```

### SMS-уведомления
```cmd
# Вручную
python manage.py send_expiry_notifications

# Автозапуск через планировщик задач
send_sms_daily.bat
```

---

## 📚 Документация

- [DUAL_INSTANCE_SETUP.md](DUAL_INSTANCE_SETUP.md) - Настройка двух инстансов
- [TOPUP_BALANCE_GUIDE.md](TOPUP_BALANCE_GUIDE.md) - Пополнение баланса
- [SMS_SETUP_GUIDE.md](SMS_SETUP_GUIDE.md) - Настройка SMS
- [DISCOUNT_SYSTEM_GUIDE.md](DISCOUNT_SYSTEM_GUIDE.md) - Система скидок менеджеров
- [TECHNICAL_SPECIFICATION.md](TECHNICAL_SPECIFICATION.md) - Техническая документация
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Тестирование

---

## 🛠️ Технологии

- **Backend:** Django 4.0.8, Python 3.12.3
- **БД:** SQLite 3
- **Автоматизация:** Selenium 4.39.0 + webdriver-manager 4.0.2
- **Парсинг:** BeautifulSoup4 4.12.3
- **Frontend:** HTML5, CSS3, JavaScript
- **SMS:** SmsMobile API

---

## 🐛 Устранение проблем

### Сервер не запускается
```cmd
# Проверить порт
netstat -ano | findstr :8000

# Остановить процесс
taskkill /PID <PID> /F
```

### Ошибки миграций
```cmd
# Удалить БД и создать заново
del db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

### Selenium не работает
```cmd
# Обновить WebDriver
pip install webdriver-manager --upgrade
```

### Дублирование логов
Убедитесь, что в `automation.py` нет `print()` в функциях `log_info()` и `log_error()`.

---

## 📝 Лицензия

Проект разработан для TajSharaTV и Taj-IPTV.  
© 2026 Все права защищены.
