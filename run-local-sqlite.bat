@echo off
echo ============================================
echo   Running Django with SQLite (No Docker needed)
echo ============================================
echo.

cd django_app

REM Check if migrations are needed
python manage.py showmigrations --settings=pricing_agent.settings_local --plan | findstr "\[ \]" >nul 2>&1
if %errorlevel% equ 0 (
    echo Applying pending migrations...
    python manage.py migrate --settings=pricing_agent.settings_local --run-syncdb
    if %errorlevel% neq 0 (
        echo [ERROR] Migration failed!
        cd ..
        pause
        exit /b 1
    )
) else (
    echo All migrations are up to date.
)

echo.
echo Creating cache table if needed...
python manage.py createcachetable --settings=pricing_agent.settings_local 2>nul

echo.
echo ============================================
echo   Starting Django Server with SQLite
echo ============================================
echo.
echo Server URL: http://localhost:8000
echo Admin URL:  http://localhost:8000/admin
echo.
echo Using SQLite database at: django_app\db.sqlite3
echo Press Ctrl+C to stop
echo.

python manage.py runserver --settings=pricing_agent.settings_local

cd ..
pause