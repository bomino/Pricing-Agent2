@echo off
echo ============================================
echo   Stopping Docker Services
echo ============================================
echo.

REM Check if Docker is running
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Docker is not running.
    pause
    exit /b 0
)

echo Current running containers:
docker-compose -f docker-compose.simple.yml ps
echo.

echo Stopping all services...
docker-compose -f docker-compose.simple.yml down
if %errorlevel% equ 0 (
    echo [SUCCESS] All services stopped.
) else (
    echo [WARNING] Some services might not have stopped properly.
)

echo.
set /p REMOVE_VOLUMES="Remove data volumes? This will delete all database data! (y/n): "
if /i "%REMOVE_VOLUMES%"=="y" (
    echo Removing volumes...
    docker-compose -f docker-compose.simple.yml down -v
    echo [WARNING] All data volumes have been removed!
)

echo.
set /p CLEAN_IMAGES="Remove Docker images to save space? (y/n): "
if /i "%CLEAN_IMAGES%"=="y" (
    echo Removing images...
    docker-compose -f docker-compose.simple.yml down --rmi local
    echo Docker images removed.
)

echo.
echo Docker services stopped.
pause