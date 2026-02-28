"""
Унифицированные настройки Django для TajSharaTV и TajIPTV
Инстанс определяется через переменную окружения INSTANCE_TYPE
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Базовая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# Определяем инстанс (по умолчанию TajSharaTV)
INSTANCE_TYPE = os.getenv('INSTANCE_TYPE', 'tajsharatv').lower()

# Загружаем соответствующий .env файл
if INSTANCE_TYPE == 'iptv':
    env_file = BASE_DIR / '.env.iptv'
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()
else:
    load_dotenv()

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Конфигурация зависит от инстанса
if INSTANCE_TYPE == 'iptv':
    # ========== IPTV CONFIGURATION ==========
    SECRET_KEY = os.getenv("SECRET_KEY_IPTV", "django-insecure-iptv-key")
    DEBUG = os.getenv("DEBUG_IPTV", "True").lower() == "true"
    ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS_IPTV", "127.0.0.1,localhost").split(",")
    
    # База данных
    DATABASES = {
        'default': {
            'ENGINE': os.getenv("DB_ENGINE_IPTV", "django.db.backends.sqlite3"),
            'NAME': os.getenv("DB_NAME_IPTV", BASE_DIR / "db_iptv.sqlite3"),
            'USER': os.getenv('DB_USER_IPTV', ''),
            'PASSWORD': os.getenv('DB_PASSWORD_IPTV', ''),
            'HOST': os.getenv('DB_HOST_IPTV', ''),
            'PORT': os.getenv('DB_PORT_IPTV', ''),
        }
    }
    
    # URL префикс
    FORCE_SCRIPT_NAME = '/iptv'
    STATIC_URL = '/iptv/static/'
    
    # Аутентификация
    LOGIN_URL = '/iptv/login/'
    LOGIN_REDIRECT_URL = '/iptv/home/'
    LOGOUT_REDIRECT_URL = '/iptv/login/'
    
    # Брендинг
    SITE_BRAND = os.getenv("SITE_BRAND_IPTV", "Taj-IPTV")
    PEER_BRAND = os.getenv("PEER_BRAND_IPTV", "TajSharaTV")
    IPTV_URL = os.getenv("IPTV_URL_IPTV", "https://tajsharatv.serveirc.com/iptv/")
    TAJSHARATTV_URL = os.getenv("TAJSHARATTV_URL_IPTV", "https://tajsharatv.serveirc.com/tajsharatv/")
    PEER_URL = TAJSHARATTV_URL
    
    # Логи
    LOG_DIR = BASE_DIR / "logs_iptv"
    
    # Дилер - включено для IPTV
    USE_DEALER_PACKAGES = True
    
else:
    # ========== TAJSHARATV CONFIGURATION ==========
    SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-local-key")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    
    # База данных
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.sqlite3'),
            'NAME': os.getenv('DB_NAME', BASE_DIR / 'db.sqlite3'),
            'USER': os.getenv('DB_USER', ''),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', ''),
            'PORT': os.getenv('DB_PORT', ''),
        }
    }
    
    # URL префикс
    FORCE_SCRIPT_NAME = '/tajsharatv'
    STATIC_URL = f'{FORCE_SCRIPT_NAME}/static/'
    
    # Аутентификация
    LOGIN_URL = '/tajsharatv/login/'
    LOGIN_REDIRECT_URL = '/tajsharatv/home/'
    LOGOUT_REDIRECT_URL = '/tajsharatv/login/'
    
    # Брендинг
    SITE_BRAND = os.getenv("SITE_BRAND", "TajSharaTV")
    PEER_BRAND = os.getenv("PEER_BRAND", "Taj-IPTV")
    IPTV_URL = os.getenv("IPTV_URL", "https://tajsharatv.serveirc.com/iptv/")
    TAJSHARATTV_URL = os.getenv("TAJSHARATTV_URL", "https://tajsharatv.serveirc.com/tajsharatv/")
    PEER_URL = IPTV_URL
    
    # Логи
    LOG_DIR = BASE_DIR / "logs"
    
    # Дилер - может быть отключено
    USE_DEALER_PACKAGES = os.getenv('USE_DEALER_PACKAGES', 'True').lower() == 'true'

# Создаём директорию для логов
LOG_DIR.mkdir(exist_ok=True)

# ========== ОБЩИЕ НАСТРОЙКИ (для обоих инстансов) ==========

# Приложения
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

# Валидация паролей
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

# Статические файлы
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Переменные для Selenium-автоматизации
DEALER_LOGIN = os.getenv('DEALER_LOGIN')
DEALER_PASSWORD = os.getenv('DEALER_PASSWORD')
DEALER_URL = os.getenv('DEALER_URL', 'http://cs-promo.ru:980')
CHROMEDRIVER_PATH = os.getenv('CHROMEDRIVER_PATH')
CHROME_USER_DATA_DIR = os.getenv('CHROME_USER_DATA_DIR', str(BASE_DIR / 'chrome-profile'))

# Telegram уведомления
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_ADMIN_ID = os.getenv('TELEGRAM_ADMIN_ID')
SITE_NAME = os.getenv('SITE_NAME', 'DealerSync')

# CSRF
CSRF_FAILURE_VIEW = 'clients.views.csrf_failure'

# Логирование
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
            'level': 'INFO',
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
            'level': 'INFO',
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
            'level': 'INFO',
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
