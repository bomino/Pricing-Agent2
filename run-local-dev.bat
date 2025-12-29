@echo off
echo ============================================
echo   Django Local Development with SQLite
echo ============================================
echo.

REM Navigate to Django app directory
cd django_app

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.8+ from https://www.python.org/
    cd ..
    pause
    exit /b 1
)

echo Checking Django installation...
python -c "import django; print(f'Django {django.__version__} installed')" 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Django not found. Installing dependencies...
    pip install -r ../requirements-simple.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies!
        cd ..
        pause
        exit /b 1
    )
)

echo.
echo ============================================
echo   Step 1: Applying Database Migrations
echo ============================================
echo.
python manage.py migrate --settings=pricing_agent.settings_local
if %errorlevel% neq 0 (
    echo [ERROR] Migration failed!
    echo Trying with --run-syncdb flag...
    python manage.py migrate --settings=pricing_agent.settings_local --run-syncdb
)

echo.
echo ============================================
echo   Step 2: Creating Cache Table
echo ============================================
python manage.py createcachetable --settings=pricing_agent.settings_local 2>nul
if %errorlevel% equ 0 (
    echo Cache table created successfully.
) else (
    echo Cache table already exists or not needed.
)

echo.
echo ============================================
echo   Step 3: Checking for Superuser Account
echo ============================================
echo.
python -c "from django.contrib.auth import get_user_model; User = get_user_model(); import sys; sys.exit(0 if User.objects.filter(is_superuser=True).exists() else 1)" --settings=pricing_agent.settings_local 2>nul
if %errorlevel% neq 0 (
    echo No superuser found. Would you like to create one now?
    echo.
    set /p CREATE_SUPER="Create superuser? (y/n): "
    if /i "%CREATE_SUPER%"=="y" (
        echo.
        echo Creating superuser account...
        python manage.py createsuperuser --settings=pricing_agent.settings_local
    ) else (
        echo.
        echo You can create a superuser later with:
        echo   python manage.py createsuperuser --settings=pricing_agent.settings_local
    )
) else (
    echo Superuser account already exists.
)

echo.
echo ============================================
echo   Step 4: Collecting Static Files
echo ============================================
python manage.py collectstatic --noinput --settings=pricing_agent.settings_local 2>nul
if %errorlevel% equ 0 (
    echo Static files collected.
) else (
    echo Static files already up to date or collection skipped.
)

echo.
echo ============================================
echo   Step 5: Running Django Check
echo ============================================
python manage.py check --settings=pricing_agent.settings_local
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Django check found some issues. See above for details.
    echo The server may still work, but you should address these issues.
    echo.
    set /p CONTINUE="Continue anyway? (y/n): "
    if /i not "%CONTINUE%"=="y" (
        cd ..
        pause
        exit /b 1
    )
)

echo.
echo ============================================
echo   Starting Django Development Server
echo ============================================
echo.
echo Server URL:  http://localhost:8000
echo Admin URL:   http://localhost:8000/admin
echo Login URL:   http://localhost:8000/accounts/login/
echo Upload URL:  http://localhost:8000/data-ingestion/upload/
echo Analytics:   http://localhost:8000/analytics/
echo.
echo Using SQLite database (no Docker/PostgreSQL needed)
echo Press Ctrl+C to stop the server
echo ============================================
echo.

python manage.py runserver --settings=pricing_agent.settings_local

cd ..
pause