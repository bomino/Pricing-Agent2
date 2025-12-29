@echo off
REM ========================================
REM Quick Installation Script for Local Testing
REM ========================================

echo.
echo ============================================
echo   Quick Installation for Local Testing
echo ============================================
echo.

REM Check Python
python --version 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed!
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install minimal requirements for local testing
echo.
echo Installing minimal requirements for local testing...
pip install Django==5.0.1
pip install django-environ==0.11.2
pip install django-extensions==3.2.3
pip install django-htmx==1.17.2
pip install whitenoise==6.6.0
pip install django-widget-tweaks==1.5.0

REM Optional: Install database drivers
echo.
choice /C YN /M "Install PostgreSQL driver (psycopg2-binary)?"
if %errorlevel% equ 1 (
    pip install psycopg2-binary==2.9.9
)

echo.
echo ============================================
echo   Installation Complete!
echo ============================================
echo.
echo To start the application, run one of:
echo   - test-django.bat (simplest)
echo   - start-local.bat (with port checking)
echo   - start-local.ps1 (PowerShell version)
echo.
pause