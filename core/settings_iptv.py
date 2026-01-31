import os
from pathlib import Path
from dotenv import load_dotenv

# Подгружаем .env.iptv (специфичные переменные для IPTV инстанса)
BASE_DIR = Path(__file__).resolve().parent.parent
env_iptv_path = BASE_DIR / '.env.iptv'
if env_iptv_path.exists():
    load_dotenv(env_iptv_path)
else:
    load_dotenv()  # Загружаем обычный .env как fallback
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Отдельный секрет и хосты для IPTV инстанса
SECRET_KEY = os.getenv("SECRET_KEY_IPTV", "django-insecure-iptv-key")
DEBUG = os.getenv("DEBUG_IPTV", "True").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS_IPTV", "127.0.0.1,localhost").split(",")

# Базовые приложения
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'clients',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'clients.middleware.ActionAuditMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'clients.context_processors.announcements',
                'clients.context_processors.links',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Отдельная БД для IPTV
DATABASES = {
    'default': {
        'ENGINE': os.getenv("DB_ENGINE_IPTV", "django.db.backends.sqlite3"),
        'NAME': os.getenv("DB_NAME_IPTV", BASE_DIR / "db_iptv.sqlite3"),
    }
}

# Пароли
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Локализация
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Asia/Dushanbe'
USE_I18N = True
USE_TZ = True
LANGUAGES = [
    ('ru', 'Русский'),
    ('en', 'English'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']

# Статика
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

SITE_NAME = os.getenv('SITE_NAME', 'DealerSync')
CHROMEDRIVER_PATH = os.getenv('CHROMEDRIVER_PATH')
CSRF_FAILURE_VIEW = 'clients.views.csrf_failure'

# Telegram уведомления для IPTV инстанса
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_ADMIN_ID = os.getenv('TELEGRAM_ADMIN_ID')

# Аутентификация
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/home/'
LOGOUT_REDIRECT_URL = '/login/'

# Ссылки
IPTV_URL = os.getenv("IPTV_URL_IPTV", "http://127.0.0.1:8001/home/")
TAJSHARATV_URL = os.getenv("TAJSHARATV_URL_IPTV", "http://127.0.0.1:8000/home/")
SITE_BRAND = os.getenv("SITE_BRAND_IPTV", "Taj-IPTV")
PEER_BRAND = os.getenv("PEER_BRAND_IPTV", "TajSharaTV")
PEER_URL = os.getenv("PEER_URL_IPTV", TAJSHARATV_URL)

# Настройки для работы с дилером (автоматизация)
DEALER_URL = os.getenv("DEALER_URL", "")
DEALER_LOGIN = os.getenv("DEALER_LOGIN", "")
DEALER_PASSWORD = os.getenv("DEALER_PASSWORD", "")

# Для IPTV: ограничивать список пакетов теми, что доступны на сайте дилера
USE_DEALER_PACKAGES = True

# Логи IPTV инстанса
LOG_DIR = BASE_DIR / "logs_iptv"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] [{levelname}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'error.log',
            'encoding': 'utf-8',
            'delay': True,
            'formatter': 'verbose',
        },
        'app_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'app.log',
            'encoding': 'utf-8',
            'delay': True,
            'formatter': 'verbose',
        },
        'automation_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'automation.log',
            'encoding': 'utf-8',
            'delay': True,
            'formatter': 'verbose',
        },
        'audit_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'audit.log',
            'encoding': 'utf-8',
            'delay': True,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['error_file', 'console'],
            'level': 'ERROR',
            'propagate': True,
        },
        'automation': {
            'handlers': ['automation_file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'audit': {
            'handlers': ['audit_file'],
            'level': 'INFO',
            'propagate': False,
        },
        '': {
            'handlers': ['app_file', 'console'],
            'level': 'INFO',
        },
    },
}
