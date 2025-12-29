@echo off
echo ============================================
echo   First-Time Setup for Pricing Agent
echo ============================================
echo.
echo This script will:
echo   1. Install Python dependencies
echo   2. Set up SQLite database
echo   3. Apply all migrations
echo   4. Create a superuser account
echo   5. Load sample data (optional)
echo   6. Start the development server
echo.
pause

REM Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.8 or later from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Step 1: Installing Dependencies
echo ============================================
echo.
echo Installing required Python packages...
pip install -r requirements-simple.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install dependencies!
    echo.
    echo Try running: pip install --upgrade pip
    echo Then run this script again.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Step 2: Setting Up Database
echo ============================================
echo.
cd django_app

echo Applying database migrations...
python manage.py migrate --settings=pricing_agent.settings_local --run-syncdb
if %errorlevel% neq 0 (
    echo [ERROR] Database setup failed!
    cd ..
    pause
    exit /b 1
)

echo.
echo Creating cache tables...
python manage.py createcachetable --settings=pricing_agent.settings_local 2>nul

echo.
echo ============================================
echo   Step 3: Creating Admin Account
echo ============================================
echo.
echo You need a superuser account to access the admin panel.
echo.
python manage.py createsuperuser --settings=pricing_agent.settings_local
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Superuser creation was skipped or failed.
    echo You can create one later with:
    echo   python manage.py createsuperuser --settings=pricing_agent.settings_local
)

echo.
echo ============================================
echo   Step 4: Loading Sample Data (Optional)
echo ============================================
echo.
set /p LOAD_SAMPLE="Would you like to load sample procurement data? (y/n): "
if /i "%LOAD_SAMPLE%"=="y" (
    echo Loading sample data...
    python manage.py create_sample_procurement_data --settings=pricing_agent.settings_local 2>nul
    if %errorlevel% equ 0 (
        echo Sample data loaded successfully!
    ) else (
        echo [WARNING] Sample data loading failed or command not available.
    )
)

echo.
echo ============================================
echo   Step 5: Collecting Static Files
echo ============================================
python manage.py collectstatic --noinput --settings=pricing_agent.settings_local

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo Your Pricing Agent is ready to use!
echo.
echo URLs:
echo   Main App:    http://localhost:8000
echo   Admin Panel: http://localhost:8000/admin
echo   Login:       http://localhost:8000/accounts/login/
echo   Upload:      http://localhost:8000/data-ingestion/upload/
echo   Analytics:   http://localhost:8000/analytics/
echo.
echo Starting the development server now...
echo Press Ctrl+C to stop the server
echo ============================================
echo.

python manage.py runserver --settings=pricing_agent.settings_local

cd ..
pause