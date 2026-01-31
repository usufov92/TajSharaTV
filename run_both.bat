@echo off
REM ============================================================
REM ЗАПУСК ОБОИХ ИНСТАНСОВ (TajSharaTV + IPTV)
REM Откроет два окна: 8000 (основной) и 8001 (IPTV)
REM ============================================================

echo Запуск TajSharaTV на порту 8000...
start "TajSharaTV (8000)" cmd /k python manage.py runserver 8000

echo Ожидание 2 сек перед запуском IPTV...
timeout /t 2 /nobreak

echo Запуск IPTV на порту 8001...
start "IPTV (8001)" cmd /k "set DJANGO_SETTINGS_MODULE=core.settings_iptv && python manage.py runserver 8001"

echo.
echo ============================================================
echo ✅ Оба инстанса запущены!
echo.
echo TajSharaTV:  http://127.0.0.1:8000/
echo IPTV:      http://127.0.0.1:8001/
echo.
echo В админке (/admin/) будут видны оба лога и кнопки для перехода.
echo ============================================================
