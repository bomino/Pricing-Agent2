@echo off
REM ========================================
REM AI Pricing Agent - Local Quick Start
REM Version 2.0 - Fixed to stay open
REM ========================================

setlocal enabledelayedexpansion
color 0A

echo.
echo ============================================
echo   AI Pricing Agent - Local Quick Start
echo ============================================
echo.
echo This script will start the app locally for testing.
echo.

REM Set default ports (can be overridden)
set DJANGO_PORT=8000
set FASTAPI_PORT=8001
set POSTGRES_PORT=5432
set REDIS_PORT=6379

REM ========================================
REM Check Prerequisites
REM ========================================
echo [1/4] Checking prerequisites...
echo.

REM Check Python
echo Checking Python installation...
python --version
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.11+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)
echo [OK] Python found
echo.

REM Check pip
echo Checking pip...
pip --version
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] pip is not installed!
    echo Try running: python -m ensurepip
    echo.
    pause
    exit /b 1
)
echo [OK] pip found
echo.

REM ========================================
REM Check and Handle Port Conflicts
REM ========================================
echo [2/4] Checking port availability...
echo.

REM Check Django port
netstat -an | findstr ":%DJANGO_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Port %DJANGO_PORT% is already in use!
    echo.
    echo Options:
    echo   1. Kill the process using port %DJANGO_PORT%
    echo   2. Use alternative port 8080
    echo   3. Use alternative port 8888
    echo   4. Enter custom port
    echo   5. Exit
    echo.
    choice /C 12345 /M "Select option"

    if !errorlevel! equ 1 (
        echo Attempting to free port %DJANGO_PORT%...
        for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%DJANGO_PORT% " ^| findstr "LISTENING"') do (
            echo Killing process PID: %%a
            taskkill /F /PID %%a >nul 2>&1
        )
        timeout /t 2 /nobreak >nul
    ) else if !errorlevel! equ 2 (
        set DJANGO_PORT=8080
        echo Using port 8080 for Django
    ) else if !errorlevel! equ 3 (
        set DJANGO_PORT=8888
        echo Using port 8888 for Django
    ) else if !errorlevel! equ 4 (
        set /p DJANGO_PORT="Enter port number for Django: "
    ) else (
        echo Exiting...
        pause
        exit /b 0
    )
) else (
    echo [OK] Port %DJANGO_PORT% is available for Django
)
echo.

REM ========================================
REM Setup Python Environment
REM ========================================
echo [3/4] Setting up Python environment...
echo.

REM Check for virtual environment
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Found virtual environment at venv\
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Found virtual environment at .venv\
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else (
    echo [INFO] No virtual environment found
    echo.
    choice /C YN /M "Create virtual environment"
    if !errorlevel! equ 1 (
        echo Creating virtual environment...
        python -m venv venv
        if !errorlevel! neq 0 (
            echo [ERROR] Failed to create virtual environment
            pause
            exit /b 1
        )
        call venv\Scripts\activate.bat
        echo [OK] Virtual environment created and activated
    ) else (
        echo [WARNING] Continuing without virtual environment
    )
)
echo.

REM Check Django installation
echo Checking for Django installation...
pip show django >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Django not found. Installing Django...
    pip install django
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install Django
        echo Try running: pip install django
        pause
        exit /b 1
    )
    echo [OK] Django installed
) else (
    echo [OK] Django is already installed
)
echo.

REM ========================================
REM Optional: Start Docker Services
REM ========================================
echo [INFO] Checking for Docker (optional)...
docker version >nul 2>&1
if %errorlevel% equ 0 (
    echo Docker is available.
    echo.
    choice /C YN /M "Start database services in Docker"
    if !errorlevel! equ 1 (
        echo Starting PostgreSQL and Redis...

        REM Check if docker-compose.windows.yml exists
        if exist "docker-compose.windows.yml" (
            echo Using docker-compose.windows.yml...
            docker-compose -f docker-compose.windows.yml up -d postgres redis mailhog
            if !errorlevel! neq 0 (
                echo Trying alternative command...
                docker compose -f docker-compose.windows.yml up -d postgres redis mailhog
            )
        ) else (
            echo [WARNING] docker-compose.windows.yml not found
            echo You can still use SQLite for testing
        )

        echo Waiting for services to start...
        timeout /t 5 /nobreak >nul
    ) else (
        echo [INFO] Skipping Docker services - will use SQLite
        set USE_SQLITE=1
    )
) else (
    echo [INFO] Docker not available - will use SQLite database
    set USE_SQLITE=1
)
echo.

REM ========================================
REM Start Django Application
REM ========================================
echo [4/4] Starting Django application...
echo.

REM Check if django_app directory exists
if not exist "django_app" (
    echo [ERROR] django_app directory not found!
    echo Current directory: %CD%
    echo.
    echo Please ensure you're running this script from the project root.
    echo The project structure should be:
    echo   %CD%\django_app\
    echo   %CD%\django_app\manage.py
    echo.
    pause
    exit /b 1
)

echo Entering django_app directory...
cd django_app

REM Check if manage.py exists
if not exist "manage.py" (
    echo [ERROR] manage.py not found in django_app directory!
    echo Current directory: %CD%
    echo.
    cd ..
    pause
    exit /b 1
)

REM Run migrations
echo Running database setup...
if defined USE_SQLITE (
    echo Using SQLite database (no Docker required)
    python manage.py migrate --run-syncdb
) else (
    echo Using PostgreSQL database
    python manage.py migrate
)

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Migration had issues, but continuing...
    echo This might be normal for first run or SQLite setup
)

echo.
echo ============================================
echo   Starting Django Development Server
echo ============================================
echo.
echo Django URL: http://localhost:%DJANGO_PORT%
echo Admin URL:  http://localhost:%DJANGO_PORT%/admin
echo.
echo To stop the server: Press Ctrl+C
echo.
echo Starting server now...
echo.

REM Start Django with custom port
python manage.py runserver 0.0.0.0:%DJANGO_PORT%

REM After Django stops
cd ..

echo.
echo ============================================
echo   Django Server Stopped
echo ============================================
echo.
echo Server has been stopped.
echo.
pause