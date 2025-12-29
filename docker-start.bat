@echo off
echo ============================================
echo   Docker-based Pricing Agent Startup
echo ============================================
echo.

REM Check if Docker is installed and running
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running or not installed!
    echo.
    echo Please ensure Docker Desktop is:
    echo   1. Installed: https://www.docker.com/products/docker-desktop
    echo   2. Running (check system tray)
    echo   3. Set to use WSL 2 backend (recommended)
    echo.
    echo Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
    if %errorlevel% equ 0 (
        echo Docker Desktop launch attempted.
        echo Waiting 30 seconds for Docker to start...
        timeout /t 30 /nobreak >nul
        docker version >nul 2>&1
        if %errorlevel% neq 0 (
            echo [ERROR] Docker still not responding. Please start it manually.
            pause
            exit /b 1
        )
    ) else (
        echo [ERROR] Could not start Docker Desktop automatically.
        echo Please start Docker Desktop manually and try again.
        pause
        exit /b 1
    )
)

echo Docker is running!
echo.

REM Check for existing containers
echo Checking for existing containers...
docker ps -a --filter "name=pricing_" --format "table {{.Names}}\t{{.Status}}" 2>nul
echo.

REM Stop existing containers if running
echo Stopping any existing containers...
docker-compose -f docker-compose.simple.yml down 2>nul
echo.

REM Clean up orphaned containers
docker container prune -f >nul 2>&1

REM Build images if needed
echo ============================================
echo   Building Docker Images (if needed)
echo ============================================
docker-compose -f docker-compose.simple.yml build --no-cache django
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to build Docker images!
    echo Trying without cache...
    docker-compose -f docker-compose.simple.yml build django
    if %errorlevel% neq 0 (
        echo [ERROR] Build failed. Check the error messages above.
        pause
        exit /b 1
    )
)

echo.
echo ============================================
echo   Starting Services
echo ============================================
echo Starting PostgreSQL, Redis, and other services...
docker-compose -f docker-compose.simple.yml up -d postgres redis mailhog
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start support services!
    pause
    exit /b 1
)

echo Waiting for PostgreSQL to be ready...
timeout /t 10 /nobreak >nul

REM Start Django
echo.
echo Starting Django application...
docker-compose -f docker-compose.simple.yml up -d django
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start Django!
    echo.
    echo Checking logs...
    docker-compose -f docker-compose.simple.yml logs --tail=50 django
    pause
    exit /b 1
)

REM Optional: Start Celery
echo.
set /p START_CELERY="Start Celery worker for background tasks? (y/n): "
if /i "%START_CELERY%"=="y" (
    echo Starting Celery worker...
    docker-compose -f docker-compose.simple.yml up -d celery
)

echo.
echo ============================================
echo   Services Status
echo ============================================
docker-compose -f docker-compose.simple.yml ps
echo.

REM Run migrations
echo ============================================
echo   Running Database Migrations
echo ============================================
docker exec pricing_django python manage.py migrate
if %errorlevel% neq 0 (
    echo [WARNING] Migrations might have issues. Check logs above.
)

echo.
echo ============================================
echo   Checking for Superuser
echo ============================================
docker exec pricing_django python -c "from django.contrib.auth import get_user_model; User = get_user_model(); import sys; sys.exit(0 if User.objects.filter(is_superuser=True).exists() else 1)" 2>nul
if %errorlevel% neq 0 (
    echo No superuser found.
    set /p CREATE_SUPER="Create superuser account? (y/n): "
    if /i "%CREATE_SUPER%"=="y" (
        echo.
        docker exec -it pricing_django python manage.py createsuperuser
    )
)

echo.
echo ============================================
echo   Application Ready!
echo ============================================
echo.
echo Access your application at:
echo   Main App:     http://localhost:8000
echo   Admin Panel:  http://localhost:8000/admin
echo   Login:        http://localhost:8000/accounts/login/
echo   Data Upload:  http://localhost:8000/data-ingestion/upload/
echo   Analytics:    http://localhost:8000/analytics/
echo.
echo Email testing interface:
echo   MailHog:      http://localhost:8025
echo.
echo Database:
echo   PostgreSQL:   localhost:5432
echo   Database:     pricing_agent
echo   User:         pricing_user
echo   Password:     pricing_password
echo.
echo ============================================
echo.
echo To view logs:
echo   docker-compose -f docker-compose.simple.yml logs -f django
echo.
echo To stop all services:
echo   docker-compose -f docker-compose.simple.yml down
echo.
echo To enter Django shell:
echo   docker exec -it pricing_django python manage.py shell
echo.
pause