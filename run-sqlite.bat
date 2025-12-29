@echo off
echo ============================================
echo   Quick Start with SQLite Database
echo ============================================
echo.

REM Set Django to use local settings
set DJANGO_SETTINGS_MODULE=pricing_agent.settings_local

cd django_app

REM Run migrations
echo Setting up database...
python manage.py migrate --run-syncdb

REM Start server
echo.
echo Starting server at http://localhost:8000
echo.
python manage.py runserver

cd ..
pause