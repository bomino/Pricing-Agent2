@echo off
echo ============================================
echo Testing Django Server - Should work now!
echo ============================================
echo.
cd django_app
echo Running Django check...
python manage.py check
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Django check failed!
    echo Please check the error messages above.
    cd ..
    pause
    exit /b 1
)
echo.
echo [SUCCESS] Django check passed!
echo.
echo Starting Django server on http://localhost:8000
echo Press Ctrl+C to stop the server
echo.
python manage.py runserver
cd ..
pause