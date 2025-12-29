@echo off
REM ========================================
REM AI Pricing Agent - Windows Startup Script
REM Version: 2.1 - Enhanced error handling
REM ========================================

setlocal enabledelayedexpansion
color 0A

echo.
echo ============================================
echo   AI Pricing Agent - Windows Startup Script
echo ============================================
echo.

REM Set error flag
set ERROR_OCCURRED=0

REM ========================================
REM STEP 1: Prerequisites Check
REM ========================================
echo [CHECKING] Prerequisites...
echo.

REM Check Python installation
echo Checking Python...
python --version 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.11+ from https://www.python.org/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    set ERROR_OCCURRED=1
    goto END_WITH_ERROR
)
echo [OK] Python is installed
echo.

REM Check pip installation
echo Checking pip...
pip --version
if %errorlevel% neq 0 (
    echo [ERROR] pip is not installed!
    echo Try running: python -m ensurepip
    echo.
    set ERROR_OCCURRED=1
    goto END_WITH_ERROR
)
echo [OK] pip is installed
echo.

REM Check if Docker Desktop is running
echo Checking Docker...
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Docker Desktop is not running!
    echo.
    echo Would you like to:
    echo   1. Try to start Docker Desktop automatically
    echo   2. Start Docker Desktop manually and retry
    echo   3. Continue without Docker (limited functionality)
    echo   4. Exit
    echo.
    choice /C 1234 /M "Select option"

    if !errorlevel! equ 1 (
        echo Attempting to start Docker Desktop...
        REM Try multiple possible locations
        if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
            start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        ) else if exist "%LOCALAPPDATA%\Docker\Docker Desktop.exe" (
            start "" "%LOCALAPPDATA%\Docker\Docker Desktop.exe"
        ) else (
            echo Could not find Docker Desktop executable.
            echo Please start Docker Desktop manually.
        )
        echo.
        echo Waiting 30 seconds for Docker to start...
        timeout /t 30

        docker version >nul 2>&1
        if !errorlevel! neq 0 (
            echo Docker still not ready. Please ensure Docker Desktop is fully started.
            set ERROR_OCCURRED=1
            goto END_WITH_ERROR
        )
    ) else if !errorlevel! equ 2 (
        echo Please start Docker Desktop and run this script again.
        set ERROR_OCCURRED=1
        goto END_WITH_ERROR
    ) else if !errorlevel! equ 3 (
        echo [WARNING] Continuing without Docker - some features will be unavailable
        set NO_DOCKER=1
    ) else (
        goto END_SCRIPT
    )
) else (
    echo [OK] Docker is running
    set NO_DOCKER=0
)
echo.

REM Check port availability
echo Checking port availability...
netstat -an | findstr ":8000 " >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Port 8000 is already in use!
    echo Django may not start properly.
    echo.
    choice /C YN /M "Do you want to continue anyway"
    if !errorlevel! equ 2 (
        set ERROR_OCCURRED=1
        goto END_WITH_ERROR
    )
)

netstat -an | findstr ":8001 " >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Port 8001 is already in use!
    echo FastAPI may not start properly.
    echo.
    choice /C YN /M "Do you want to continue anyway"
    if !errorlevel! equ 2 (
        set ERROR_OCCURRED=1
        goto END_WITH_ERROR
    )
)
echo [OK] Ports are available
echo.

REM ========================================
REM STEP 2: Docker Setup
REM ========================================
if %NO_DOCKER% equ 1 (
    echo [SKIPPING] Docker setup - running in local-only mode
    set RUN_LOCAL=1
    goto DJANGO_SETUP
)

echo ========================================
echo   STEP 2: Docker Setup
echo ========================================
echo.

REM Choose Docker Compose file
echo Select Docker configuration:
echo   1. Windows Development (PostgreSQL, Redis, MailHog only)
echo   2. Full Docker Setup (All services in containers)
echo.
choice /C 12 /T 10 /D 1 /M "Select option (defaults to 1 in 10 seconds)"
set DOCKER_CHOICE=!errorlevel!

if !DOCKER_CHOICE! equ 1 (
    echo [INFO] Using Windows development configuration...
    set COMPOSE_FILE=docker-compose.windows.yml
    set RUN_LOCAL=1
) else (
    echo [INFO] Using full Docker configuration...
    set COMPOSE_FILE=docker-compose.simple.yml
    set RUN_LOCAL=0
)

echo [INFO] Starting Docker containers using !COMPOSE_FILE!...
docker-compose -f !COMPOSE_FILE! up -d
if !errorlevel! neq 0 (
    echo [ERROR] Failed to start Docker containers!
    echo.
    echo Trying alternative docker compose command...
    docker compose -f !COMPOSE_FILE! up -d
    if !errorlevel! neq 0 (
        echo [ERROR] Both docker-compose and docker compose commands failed!
        echo Please check:
        echo   1. Docker Desktop is running
        echo   2. The file !COMPOSE_FILE! exists
        echo   3. You have sufficient disk space
        echo.
        set ERROR_OCCURRED=1
        goto END_WITH_ERROR
    )
)

REM Wait for PostgreSQL to be ready
echo [INFO] Waiting for PostgreSQL to be ready...
set RETRIES=0
:WAIT_POSTGRES
if !RETRIES! geq 30 (
    echo [WARNING] PostgreSQL is taking longer than expected to start
    echo You can check the logs with: docker-compose -f !COMPOSE_FILE! logs postgres
    echo.
    choice /C YN /M "Continue anyway"
    if !errorlevel! equ 2 (
        set ERROR_OCCURRED=1
        goto END_WITH_ERROR
    )
    goto POSTGRES_DONE
)
timeout /t 2 /nobreak >nul
docker exec pricing_postgres pg_isready -U pricing_user >nul 2>&1
if !errorlevel! neq 0 (
    set /a RETRIES+=1
    echo [WAITING] PostgreSQL is starting... (!RETRIES!/30)
    goto WAIT_POSTGRES
)
:POSTGRES_DONE
echo [OK] PostgreSQL is ready!

REM Check Redis
echo [INFO] Checking Redis...
docker exec pricing_redis redis-cli ping >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Redis is ready!
) else (
    echo [WARNING] Redis may not be ready yet
)
echo.

:DJANGO_SETUP
REM ========================================
REM STEP 3: Django Setup
REM ========================================
echo ========================================
echo   STEP 3: Django Setup
echo ========================================
echo.

if %RUN_LOCAL% equ 1 (
    REM Check for virtual environment
    if exist "venv\Scripts\activate.bat" (
        echo [INFO] Found virtual environment at venv\
        call venv\Scripts\activate.bat
    ) else if exist ".venv\Scripts\activate.bat" (
        echo [INFO] Found virtual environment at .venv\
        call .venv\Scripts\activate.bat
    ) else (
        echo [INFO] No virtual environment found.
        choice /C YN /T 10 /D N /M "Create a virtual environment? (N in 10 seconds)"
        if !errorlevel! equ 1 (
            echo [INFO] Creating virtual environment...
            python -m venv venv
            if !errorlevel! neq 0 (
                echo [ERROR] Failed to create virtual environment
                echo Continuing without virtual environment...
            ) else (
                call venv\Scripts\activate.bat
                echo [OK] Virtual environment created and activated
            )
        )
    )
    echo.

    REM Check and install requirements
    echo [INFO] Checking Python dependencies...
    pip show django >nul 2>&1
    if !errorlevel! neq 0 (
        echo [INFO] Django not found. Installing requirements...
        if exist "requirements-simple.txt" (
            echo Installing from requirements-simple.txt...
            pip install -r requirements-simple.txt
        ) else if exist "requirements.txt" (
            echo Installing from requirements.txt...
            pip install -r requirements.txt
        ) else (
            echo [WARNING] No requirements file found!
            echo Installing minimal requirements...
            pip install django
        )
    ) else (
        echo [OK] Dependencies appear to be installed
    )
    echo.

    REM Only run migrations if we have database
    if %NO_DOCKER% equ 0 (
        REM Check if migrations are needed
        echo [INFO] Checking database migrations...
        cd django_app 2>nul
        if !errorlevel! neq 0 (
            echo [ERROR] django_app directory not found!
            echo Current directory: %CD%
            set ERROR_OCCURRED=1
            goto END_WITH_ERROR
        )

        python manage.py showmigrations --plan >nul 2>&1
        if !errorlevel! neq 0 (
            echo [WARNING] Could not check migrations
            echo Running migrate anyway...
        )

        echo [INFO] Running database migrations...
        python manage.py migrate
        if !errorlevel! neq 0 (
            echo [WARNING] Migration failed - this might be normal for first run
        ) else (
            echo [OK] Migrations completed
        )

        REM Check for superuser
        python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); exit(0 if User.objects.filter(is_superuser=True).exists() else 1)" >nul 2>&1
        if !errorlevel! neq 0 (
            echo [INFO] No superuser found.
            choice /C YN /T 10 /D N /M "Create a superuser account? (N in 10 seconds)"
            if !errorlevel! equ 1 (
                echo.
                echo Creating superuser account...
                python manage.py createsuperuser
            )
        )

        REM Collect static files
        echo [INFO] Collecting static files...
        python manage.py collectstatic --noinput >nul 2>&1

        cd ..
    ) else (
        echo [WARNING] Skipping database operations (no Docker)
    )
) else (
    REM For full Docker setup, run commands in container
    echo [INFO] Running migrations in Docker container...
    docker exec pricing_django python manage.py migrate

    echo [INFO] Collecting static files in Docker container...
    docker exec pricing_django python manage.py collectstatic --noinput

    REM Check for superuser in container
    docker exec pricing_django python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); exit(0 if User.objects.filter(is_superuser=True).exists() else 1)" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [INFO] No superuser found.
        choice /C YN /T 10 /D N /M "Create a superuser account? (N in 10 seconds)"
        if !errorlevel! equ 1 (
            docker exec -it pricing_django python manage.py createsuperuser
        )
    )
)

echo.
echo ========================================
echo   STEP 4: Starting Application Servers
echo ========================================
echo.

if %RUN_LOCAL% equ 1 (
    echo [INFO] Starting local Django server...
    start "Django Server" cmd /k "cd django_app && python manage.py runserver 0.0.0.0:8000"

    timeout /t 2 /nobreak >nul

    REM Check if FastAPI directory exists
    if exist "fastapi_ml\main.py" (
        echo [INFO] Starting local FastAPI ML service...
        start "FastAPI ML Service" cmd /k "cd fastapi_ml && uvicorn main:app --reload --host 0.0.0.0 --port 8001"
    ) else (
        echo [INFO] FastAPI ML service not found - skipping
    )

    REM Start Celery workers (optional)
    echo.
    choice /C YN /T 10 /D N /M "Start Celery workers? (N in 10 seconds)"
    if !errorlevel! equ 1 (
        echo [INFO] Starting Celery workers...
        start "Celery Worker" cmd /k "cd django_app && celery -A pricing_agent worker --loglevel=info --pool=solo"
        start "Celery Beat" cmd /k "cd django_app && celery -A pricing_agent beat --loglevel=info"
    )
) else (
    echo [OK] All services running in Docker containers
)

echo.
echo ============================================
echo   All services started successfully!
echo ============================================
echo.
echo Services running:

if %NO_DOCKER% equ 0 (
    echo   PostgreSQL........: localhost:5432
    echo   Redis.............: localhost:6379
    echo   MailHog (Email)...: http://localhost:8025
)

echo.
if %RUN_LOCAL% equ 1 (
    echo   Django Application: http://localhost:8000
    echo   Django Admin......: http://localhost:8000/admin
    if exist "fastapi_ml\main.py" (
        echo   FastAPI ML Service: http://localhost:8001
        echo   FastAPI Docs......: http://localhost:8001/docs
    )
) else (
    echo   Django Application: http://localhost:8000 (Docker)
    echo   Django Admin......: http://localhost:8000/admin
    echo   FastAPI ML Service: http://localhost:8001 (Docker)
    echo   FastAPI Docs......: http://localhost:8001/docs
)

echo.
echo ============================================
echo   Quick Access Links:
echo ============================================
echo.
echo   1. Main Dashboard....: http://localhost:8000
echo   2. Analytics Center..: http://localhost:8000/analytics/
echo   3. Data Upload.......: http://localhost:8000/data-ingestion/upload/
echo   4. Admin Panel.......: http://localhost:8000/admin

if %NO_DOCKER% equ 0 (
    echo   5. API Documentation.: http://localhost:8001/docs
    echo   6. Email Testing.....: http://localhost:8025
)

echo.
echo To stop all services, run: stop-windows.bat
echo.
goto END_SCRIPT

:END_WITH_ERROR
echo.
echo ============================================
echo   Script encountered errors!
echo ============================================
echo.
echo Please review the error messages above.
echo.
echo Common solutions:
echo   1. Run as Administrator
echo   2. Ensure Docker Desktop is running
echo   3. Check Python installation
echo   4. Free up ports 8000 and 8001
echo.

:END_SCRIPT
echo.
echo Press any key to exit...
pause
exit /b %ERROR_OCCURRED%