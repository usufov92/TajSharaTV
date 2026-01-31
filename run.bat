@echo off
chcp 65001 > nul
echo ========================================
echo   TajSharaTV - IPTV Management System
echo ========================================
echo.
echo Запуск сервера разработки...
echo Сервер будет доступен по адресу: http://127.0.0.1:8000
echo.
echo Для остановки нажмите Ctrl+C
echo ========================================
echo.

python manage.py runserver 8000

pause
