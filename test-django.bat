@echo off
REM Quick Django Test Script
echo.
echo Testing Django Application...
echo.

cd django_app
python manage.py runserver
cd ..

pause