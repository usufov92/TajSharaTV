@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Обновление базы данных
echo   TajSharaTV - IPTV Management System
echo ========================================
echo.
echo Эта операция применит следующие изменения:
echo   - Добавит поле "comment" в Transaction
echo   - Сделает поле "client" опциональным
echo   - Уберет валидатор MinValue с total_cost
echo.
echo Нажмите любую клавишу для продолжения...
pause >nul

echo.
echo Применяем миграции...
python manage.py migrate

echo.
echo ========================================
if %errorlevel% equ 0 (
    echo   ✅ Миграции применены успешно!
    echo   Теперь вы можете использовать функцию пополнения баланса
) else (
    echo   ❌ Ошибка при применении миграций
    echo   Проверьте вывод выше для деталей
)
echo ========================================
echo.
pause
