@echo off
echo ============================================
echo   Docker Environment Test
echo ============================================
echo.

echo [1/5] Checking Docker installation...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Docker not found
    echo    Please install Docker Desktop from https://www.docker.com/
    goto :summary
) else (
    docker --version
    echo    ✅ Docker installed
)

echo.
echo [2/5] Checking Docker daemon...
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Docker daemon not running
    echo    Please start Docker Desktop
    goto :summary
) else (
    echo    ✅ Docker daemon running
)

echo.
echo [3/5] Checking docker-compose...
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ docker-compose not found
    goto :summary
) else (
    docker-compose --version
    echo    ✅ docker-compose installed
)

echo.
echo [4/5] Checking Docker compose file...
if exist "docker-compose.simple.yml" (
    echo    ✅ docker-compose.simple.yml found
) else (
    echo    ❌ docker-compose.simple.yml not found
    echo    Are you in the right directory?
    goto :summary
)

echo.
echo [5/5] Checking port availability...
netstat -an | findstr :8000 | findstr LISTENING >nul 2>&1
if %errorlevel% equ 0 (
    echo    ⚠️  Port 8000 is already in use
    echo    Run 'netstat -ano | findstr :8000' to find the process
) else (
    echo    ✅ Port 8000 is available
)

netstat -an | findstr :5432 | findstr LISTENING >nul 2>&1
if %errorlevel% equ 0 (
    echo    ⚠️  Port 5432 is already in use (PostgreSQL)
) else (
    echo    ✅ Port 5432 is available
)

:summary
echo.
echo ============================================
echo   Test Summary
echo ============================================
echo.

docker version >nul 2>&1
if %errorlevel% equ 0 (
    docker ps >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Docker is ready!
        echo.
        echo You can now run: docker-start.bat
    ) else (
        echo ❌ Docker Desktop is not running
        echo Please start Docker Desktop and try again
    )
) else (
    echo ❌ Docker is not installed
    echo Please install Docker Desktop first
)

echo.
pause