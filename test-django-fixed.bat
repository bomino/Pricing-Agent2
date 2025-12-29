@echo off
echo Testing Django after fixing import errors...
echo.
cd django_app
echo Running Django check command...
python manage.py check
echo.
if %errorlevel% equ 0 (
    echo Django check passed! Starting server...
    echo.
    python manage.py runserver
) else (
    echo Django check failed. See errors above.
)
cd ..
pause