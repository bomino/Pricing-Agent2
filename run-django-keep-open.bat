@echo off
title Django Server - DO NOT CLOSE
color 0A

echo ============================================
echo Starting Django Server
echo ============================================
echo.

REM Try to change to django_app
cd django_app 2>error.txt

REM If that failed, show error
if not exist "manage.py" (
    echo ERROR: Cannot find manage.py
    echo.
    echo Current directory: %CD%
    echo.
    echo Error details:
    type error.txt
    echo.
    echo Press any key to try anyway...
    pause
)

echo Running Django server...
echo.

REM Run Django and capture any errors
python manage.py runserver 2>&1

echo.
echo ============================================
echo Django stopped or failed to start
echo ============================================
echo.
echo If Django failed to start, check the error messages above.
echo.
echo Common issues:
echo 1. Django not installed - run: pip install django
echo 2. Missing dependencies - run: pip install -r requirements-simple.txt
echo 3. Database issues - try: python manage.py migrate
echo.

REM Keep window open indefinitely
:KEEPOPEN
echo Press Ctrl+C to close this window...
pause >nul
goto KEEPOPEN