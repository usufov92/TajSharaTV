#!/bin/bash
# Запуск TajSharaTV инстанса на порту 8000

cd /home/tajshara/TajSharaTV

# Останавливаем старые процессы на порту 8000
pkill -f "gunicorn.*8000" 2>/dev/null

# Запускаем Gunicorn с переменной окружения INSTANCE_TYPE
nohup venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --timeout 300 \
    --env INSTANCE_TYPE=tajsharatv \
    --access-logfile logs/gunicorn_access.log \
    --error-logfile logs/gunicorn_error.log \
    core.wsgi:application > /dev/null 2>&1 &

echo "✅ TajSharaTV запущен на порту 8000"
echo "PID: $(pgrep -f 'gunicorn.*8000' | head -1)"
