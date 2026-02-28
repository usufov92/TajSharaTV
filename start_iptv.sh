#!/bin/bash
# Запуск TajIPTV инстанса на порту 8001

cd /home/tajshara/TajSharaTV

# Останавливаем старые процессы на порту 8001
pkill -f "gunicorn.*8001" 2>/dev/null

# Запускаем Gunicorn с переменной окружения INSTANCE_TYPE
nohup venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8001 \
    --timeout 300 \
    --env INSTANCE_TYPE=iptv \
    --access-logfile logs_iptv/gunicorn_access.log \
    --error-logfile logs_iptv/gunicorn_error.log \
    core.wsgi:application > /dev/null 2>&1 &

echo "✅ TajIPTV запущен на порту 8001"
echo "PID: $(pgrep -f 'gunicorn.*8001' | head -1)"
