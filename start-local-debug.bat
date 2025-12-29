@echo off
REM ========================================
REM DEBUG VERSION - Will show all errors
REM ========================================

color 0A

echo ============================================
echo   AI Pricing Agent - DEBUG VERSION
echo ============================================
echo.
echo This script will show exactly what's happening
echo.
pause

echo.
echo Step 1: Checking Python...
echo ----------------------------------------
where python
python --version

echo.
echo Step 2: Checking pip...
echo ----------------------------------------
where pip
pip --version

echo.
echo Step 3: Current Directory...
echo ----------------------------------------
echo Current location: %CD%
dir /b

echo.
echo Step 4: Checking for django_app folder...
echo ----------------------------------------
if exist "django_app" (
    echo Found django_app folder!
    dir django_app /b
) else (
    echo ERROR: django_app folder not found!
    echo Looking for Django directories...
    dir /b /ad
)

echo.
echo Step 5: Trying to enter django_app...
echo ----------------------------------------
cd django_app
echo Current directory after cd: %CD%

echo.
echo Step 6: Checking for manage.py...
echo ----------------------------------------
if exist "manage.py" (
    echo Found manage.py!
) else (
    echo ERROR: manage.py not found!
    echo Files in current directory:
    dir /b *.py
)

echo.
echo Step 7: Checking Django installation...
echo ----------------------------------------
pip show django

echo.
echo Step 8: Trying to run Django...
echo ----------------------------------------
echo Running: python manage.py runserver
echo.
python manage.py runserver

echo.
echo ============================================
echo Script finished - check errors above
echo ============================================
pause