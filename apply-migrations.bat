@echo off
echo ============================================
echo   Applying Django Migrations (SQLite)
echo ============================================
echo.

cd django_app

echo Running migrations for SQLite database...
python manage.py migrate --settings=pricing_agent.settings_local
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Standard migration failed. Trying with --run-syncdb...
    python manage.py migrate --settings=pricing_agent.settings_local --run-syncdb
    if %errorlevel% neq 0 (
        echo [ERROR] Migration failed! Check the error messages above.
        cd ..
        pause
        exit /b 1
    )
)

echo.
echo ============================================
echo   Migration Summary
echo ============================================
python manage.py showmigrations --settings=pricing_agent.settings_local

echo.
echo ============================================
echo   Database Tables Created
echo ============================================
python -c "from django.db import connection; cursor = connection.cursor(); cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;\"); tables = cursor.fetchall(); print('\n'.join([t[0] for t in tables]))" --settings=pricing_agent.settings_local

echo.
echo [SUCCESS] All migrations applied successfully!
echo.
echo You can now run the server with:
echo   run-local-dev.bat
echo.
cd ..
pause