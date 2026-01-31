@echo off
REM Скрипт для автоматической отправки SMS-уведомлений клиентам
REM Запускается 3 раза в день (утро, обед, вечер) через Task Scheduler
REM Проверка: если SMS уже отправлено сегодня, второй запуск не будет отправлять дубликаты

cd /d "c:\Users\musuf\OneDrive\Рабочий стол\Projects\на разработка для атоматизация\dealer-sync"

REM Активация виртуального окружения (если используется)
REM call venv\Scripts\activate.bat

REM Запуск команды отправки SMS с проверкой дубликатов за день
python manage.py send_expiry_notifications >> logs\sms_notifications.log 2>&1

REM Деактивация виртуального окружения
REM deactivate

echo SMS проверка завершена: %date% %time% >> logs\sms_notifications.log
