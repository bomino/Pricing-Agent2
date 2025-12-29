@echo off
echo ============================================
echo   Starting PostgreSQL in Docker
echo ============================================
echo.

REM Check if Docker is running
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop first.
    pause
    exit /b 1
)

echo Starting PostgreSQL container...

REM Try docker-compose first
if exist "docker-compose.windows.yml" (
    docker-compose -f docker-compose.windows.yml up -d postgres
) else (
    REM Start standalone PostgreSQL container
    docker run -d ^
        --name pricing_postgres ^
        -p 5432:5432 ^
        -e POSTGRES_USER=pricing_user ^
        -e POSTGRES_PASSWORD=pricing_password ^
        -e POSTGRES_DB=pricing_agent ^
        postgres:16-alpine
)

echo.
echo Waiting for PostgreSQL to be ready...
timeout /t 5

echo.
echo PostgreSQL should be running on port 5432
echo.
echo Now you can run Django with PostgreSQL:
echo   cd django_app
echo   python manage.py migrate
echo   python manage.py runserver
echo.
pause