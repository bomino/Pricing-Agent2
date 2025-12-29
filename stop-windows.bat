@echo off
REM ========================================
REM AI Pricing Agent - Windows Stop Script
REM Version: 2.0
REM ========================================

setlocal enabledelayedexpansion
color 0C

echo.
echo ============================================
echo   AI Pricing Agent - Windows Stop Script
echo ============================================
echo.

REM ========================================
REM STEP 1: Stop Application Processes
REM ========================================
echo [STOPPING] Application processes...
echo.

REM Kill Django processes
echo [INFO] Stopping Django server...
taskkill /FI "WINDOWTITLE eq Django Server*" /F >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Django server stopped
) else (
    echo [INFO] Django server was not running
)

REM Kill FastAPI processes
echo [INFO] Stopping FastAPI ML service...
taskkill /FI "WINDOWTITLE eq FastAPI ML Service*" /F >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] FastAPI ML service stopped
) else (
    echo [INFO] FastAPI ML service was not running
)

REM Kill Celery processes
echo [INFO] Stopping Celery workers...
taskkill /FI "WINDOWTITLE eq Celery Worker*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Celery Beat*" /F >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Celery workers stopped
) else (
    echo [INFO] Celery workers were not running
)

REM Kill any remaining Python processes (with confirmation)
echo.
echo [WARNING] Checking for remaining Python processes...
tasklist | findstr "python.exe" >nul 2>&1
if %errorlevel% equ 0 (
    echo Found running Python processes.
    echo This may include other Python applications you have running.
    choice /C YN /M "Do you want to stop ALL Python processes"
    if !errorlevel! equ 1 (
        taskkill /IM python.exe /F >nul 2>&1
        echo [OK] All Python processes stopped
    ) else (
        echo [SKIPPED] Python processes left running
    )
) else (
    echo [OK] No Python processes found
)

echo.
echo ========================================
echo   STEP 2: Stop Docker Containers
echo ========================================
echo.

REM Check if Docker is running
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Docker is not running or not accessible
    echo Skipping Docker container cleanup
    goto CLEANUP
)

REM Check which docker-compose files have running containers
echo [INFO] Checking for running Docker containers...

REM Try docker-compose.windows.yml first
docker-compose -f docker-compose.windows.yml ps -q >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Stopping containers from docker-compose.windows.yml...
    docker-compose -f docker-compose.windows.yml down -v
    if %errorlevel% equ 0 (
        echo [OK] Windows Docker containers stopped
    ) else (
        echo [WARNING] Failed to stop some Windows Docker containers
    )
)

REM Try docker-compose.simple.yml
docker-compose -f docker-compose.simple.yml ps -q >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Stopping containers from docker-compose.simple.yml...
    docker-compose -f docker-compose.simple.yml down -v
    if %errorlevel% equ 0 (
        echo [OK] Simple Docker containers stopped
    ) else (
        echo [WARNING] Failed to stop some Simple Docker containers
    )
)

REM Check for any remaining pricing-related containers
echo [INFO] Checking for orphaned containers...
docker ps -a --filter "name=pricing" --format "{{.Names}}" >temp_containers.txt 2>nul
set FOUND_CONTAINERS=0
for /f %%i in (temp_containers.txt) do (
    set FOUND_CONTAINERS=1
    echo [INFO] Stopping orphaned container: %%i
    docker stop %%i >nul 2>&1
    docker rm %%i >nul 2>&1
)
del temp_containers.txt >nul 2>&1

if %FOUND_CONTAINERS% equ 0 (
    echo [OK] No orphaned containers found
) else (
    echo [OK] Orphaned containers cleaned up
)

:CLEANUP
echo.
echo ========================================
echo   STEP 3: Port Cleanup Check
echo ========================================
echo.

REM Check if ports are still in use
echo [INFO] Checking port status...

netstat -an | findstr ":8000 " >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Port 8000 is still in use
    echo You may need to manually stop the process using this port
) else (
    echo [OK] Port 8000 is free
)

netstat -an | findstr ":8001 " >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Port 8001 is still in use
    echo You may need to manually stop the process using this port
) else (
    echo [OK] Port 8001 is free
)

netstat -an | findstr ":5432 " >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Port 5432 (PostgreSQL) may still be in use
) else (
    echo [OK] Port 5432 is free
)

netstat -an | findstr ":6379 " >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Port 6379 (Redis) may still be in use
) else (
    echo [OK] Port 6379 is free
)

echo.
echo ============================================
echo   All services stopped!
echo ============================================
echo.
echo Cleanup complete. You can now:
echo   - Run start-windows.bat to restart services
echo   - Close this window
echo.

REM Optional: Clean up temporary files
choice /C YN /T 5 /D N /M "Do you want to clean temporary files (cache, logs)"
if %errorlevel% equ 1 (
    echo [INFO] Cleaning temporary files...

    REM Clean Python cache
    if exist "__pycache__" rd /s /q "__pycache__" 2>nul
    if exist "django_app\__pycache__" rd /s /q "django_app\__pycache__" 2>nul
    if exist "fastapi_ml\__pycache__" rd /s /q "fastapi_ml\__pycache__" 2>nul

    REM Clean Django cache
    if exist "django_app\media\cache" rd /s /q "django_app\media\cache" 2>nul
    if exist "django_app\staticfiles" rd /s /q "django_app\staticfiles" 2>nul

    REM Clean logs (optional - keeping last log)
    if exist "logs" (
        echo [INFO] Preserving latest logs...
        for %%F in (logs\*.log) do (
            if not "%%~nxF"=="latest.log" del "%%F" 2>nul
        )
    )

    echo [OK] Temporary files cleaned
)

echo.
echo Press any key to exit...
pause >nul