# Windows Local Development Setup Guide

## Complete Guide for Running AI Pricing Agent on Windows

This guide will walk you through setting up and running the AI Pricing Agent system locally on Windows.

## 📋 Prerequisites

### Required Software

1. **Windows 10/11 Professional or Enterprise** (for Docker Desktop)
   - Windows Home users need WSL2 backend

2. **WSL2 (Windows Subsystem for Linux)**
   ```powershell
   # Run in PowerShell as Administrator
   wsl --install
   # Restart your computer after installation
   ```

3. **Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop
   - Enable WSL2 backend during installation
   - After installation, ensure Docker is running (whale icon in system tray)

4. **Python 3.11+**
   - Download from: https://www.python.org/downloads/
   - ✅ Check "Add Python to PATH" during installation
   - Verify: `python --version`

5. **Git for Windows**
   - Download from: https://git-scm.com/download/win
   - Use default settings during installation

6. **Visual Studio Code** (Recommended)
   - Download from: https://code.visualstudio.com/
   - Install extensions:
     - Python
     - Django
     - Docker
     - Remote - WSL

7. **PostgreSQL Client Tools** (Optional)
   - Download pgAdmin: https://www.pgadmin.org/download/

## 🚀 Step-by-Step Setup

### Step 1: Clone the Repository

Open PowerShell or Command Prompt:

```powershell
# Navigate to your projects directory
cd "C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject"

# If repository not cloned yet
git clone <your-repo-url> Pricing_Agent
cd Pricing_Agent
```

### Step 2: Set Up Environment Variables

```powershell
# Copy environment template
copy .env.example .env

# Open in notepad to edit (or use VS Code)
notepad .env
```

Update the `.env` file with these Windows-specific settings:

```env
# Windows-specific settings
DEBUG=True
SECRET_KEY=local-development-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,host.docker.internal

# Database - Using Docker containers
DATABASE_URL=postgresql://pricing_user:pricing_password@localhost:5432/pricing_agent
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pricing_agent
DB_USER=pricing_user
DB_PASSWORD=pricing_password

# Redis - Using Docker container
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# ML Service
ML_SERVICE_URL=http://localhost:8001
FASTAPI_ENV=development

# Email (for development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# File paths (Windows compatible)
MEDIA_ROOT=C:/Users/lawry/Documents/VSTX Projects/VSTX-Project/PricingProject/Pricing_Agent/media
STATIC_ROOT=C:/Users/lawry/Documents/VSTX Projects/VSTX-Project/PricingProject/Pricing_Agent/static
LOG_FILE=C:/Users/lawry/Documents/VSTX Projects/VSTX-Project/PricingProject/Pricing_Agent/logs/app.log
```

### Step 3: Create Required Directories

```powershell
# Create necessary directories
mkdir media, static, logs, django_app\static, django_app\media
mkdir fastapi_ml\ml_artifacts\models
```

### Step 4: Set Up Python Virtual Environment

```powershell
# Install Poetry (Python package manager)
pip install poetry

# Or if you prefer standard venv
python -m venv venv

# Activate virtual environment
# For Poetry:
poetry shell

# For standard venv:
.\venv\Scripts\Activate.ps1

# Note: If you get execution policy error, run:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 5: Install Python Dependencies

```powershell
# Using Poetry (recommended if pyproject.toml exists)
poetry install

# Or using pip with the appropriate requirements file
# For development (includes testing and dev tools):
pip install -r requirements\development.txt

# Or for production:
pip install -r requirements\production.txt

# Or for basic setup:
pip install -r requirements.txt

# Install additional Windows-specific packages (already included in requirements)
# These will be automatically installed if on Windows
```

### Step 6: Start Docker Containers

Create a Windows-specific Docker Compose file:

```powershell
# Create docker-compose.windows.yml
notepad docker-compose.windows.yml
```

Add this content:

```yaml
version: '3.8'

services:
  postgres:
    image: timescale/timescaledb:latest-pg16
    container_name: pricing_postgres
    environment:
      POSTGRES_DB: pricing_agent
      POSTGRES_USER: pricing_user
      POSTGRES_PASSWORD: pricing_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pricing_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: pricing_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  mailhog:
    image: mailhog/mailhog
    container_name: pricing_mailhog
    ports:
      - "1025:1025"  # SMTP server
      - "8025:8025"  # Web UI
    
volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
```

Start the containers:

```powershell
# Start Docker Desktop first (make sure it's running)

# Start containers
docker-compose -f docker-compose.windows.yml up -d

# Verify containers are running
docker ps

# You should see:
# - pricing_postgres (PostgreSQL + TimescaleDB)
# - pricing_redis (Redis)
# - pricing_mailhog (Email testing)
```

### Step 7: Initialize the Database

```powershell
# Create TimescaleDB extension
docker exec -it pricing_postgres psql -U pricing_user -d pricing_agent -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Navigate to Django app
cd django_app

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
# Follow prompts to create admin user

# Load initial data (if available)
python manage.py loaddata initial_data.json
```

### Step 8: Start the Django Development Server

Open a new PowerShell window:

```powershell
# Navigate to project
cd "C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent"

# Activate virtual environment
.\venv\Scripts\Activate.ps1  # or 'poetry shell'

# Start Django server
cd django_app
python manage.py runserver

# Server will start at http://localhost:8000
```

### Step 9: Start the FastAPI ML Service

Open another PowerShell window:

```powershell
# Navigate to project
cd "C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent"

# Activate virtual environment
.\venv\Scripts\Activate.ps1  # or 'poetry shell'

# Start FastAPI service
cd fastapi_ml
uvicorn main:app --reload --port 8001

# API documentation available at http://localhost:8001/docs
```

### Step 10: Start Celery Workers (Optional)

Open another PowerShell window:

```powershell
# Navigate to Django app
cd "C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app"

# Activate virtual environment
..\venv\Scripts\Activate.ps1

# Start Celery worker
celery -A pricing_agent worker --loglevel=info --pool=solo

# Note: We use --pool=solo on Windows as the default pool doesn't work
```

For Celery Beat (scheduled tasks), open another window:

```powershell
# Start Celery Beat
celery -A pricing_agent beat --loglevel=info
```

## 🖥️ Accessing the Application

Once everything is running, you can access:

1. **Main Application**: http://localhost:8000
2. **Django Admin**: http://localhost:8000/admin
3. **FastAPI Documentation**: http://localhost:8001/docs
4. **Email Testing (MailHog)**: http://localhost:8025
5. **pgAdmin** (if installed): Connect to `localhost:5432` with credentials from `.env`

## 🛠️ Windows-Specific Troubleshooting

### Common Issues and Solutions

#### 1. Docker Desktop Not Starting
```powershell
# Enable virtualization in BIOS
# Enable Hyper-V and WSL2 features
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Restart computer
```

#### 2. Port Already in Use
```powershell
# Check what's using the port
netstat -ano | findstr :8000

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or change the port in the command:
python manage.py runserver 8080
```

#### 3. Permission Denied Errors
```powershell
# Run PowerShell as Administrator
# Or ensure your user has full control of the project directory
```

#### 4. Python Path Issues
```powershell
# Add Python to PATH manually
$env:Path += ";C:\Users\lawry\AppData\Local\Programs\Python\Python311"
$env:Path += ";C:\Users\lawry\AppData\Local\Programs\Python\Python311\Scripts"

# Make permanent via System Properties > Environment Variables
```

#### 5. Celery Not Working on Windows
```powershell
# Install eventlet for better Windows support
pip install eventlet

# Run Celery with eventlet
celery -A pricing_agent worker --loglevel=info --pool=eventlet

# Or use --pool=solo for development
celery -A pricing_agent worker --loglevel=info --pool=solo
```

#### 6. Database Connection Issues
```powershell
# Test PostgreSQL connection
docker exec -it pricing_postgres psql -U pricing_user -d pricing_agent

# If connection fails, check Docker container logs
docker logs pricing_postgres
```

## 🔧 Development Workflow

### Daily Development Steps

1. **Start Docker Desktop** (ensure whale icon is in system tray)

2. **Start Services**:
```powershell
# Start database and Redis
docker-compose -f docker-compose.windows.yml up -d

# Start Django (Terminal 1)
cd django_app
python manage.py runserver

# Start FastAPI (Terminal 2)
cd fastapi_ml
uvicorn main:app --reload --port 8001

# Start Celery (Terminal 3 - optional)
cd django_app
celery -A pricing_agent worker --loglevel=info --pool=solo
```

3. **Stop Services**:
```powershell
# Stop Django/FastAPI: Press Ctrl+C in each terminal

# Stop Docker containers
docker-compose -f docker-compose.windows.yml down

# Stop all containers (if needed)
docker stop $(docker ps -q)
```

### Using VS Code

1. **Open Project**:
```powershell
# Open VS Code in project directory
code .
```

2. **Recommended VS Code Settings** (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}\\venv\\Scripts\\python.exe",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "files.eol": "\n",
  "terminal.integrated.defaultProfile.windows": "PowerShell"
}
```

3. **Debugging in VS Code**:
   - Use the Python extension's debugging features
   - Set breakpoints in your code
   - Press F5 to start debugging

## 📝 Quick Commands Reference

```powershell
# Start everything
docker-compose -f docker-compose.windows.yml up -d
python django_app\manage.py runserver
# (In new terminal)
uvicorn fastapi_ml.main:app --reload --port 8001

# Run tests
python django_app\manage.py test
pytest fastapi_ml\tests\

# Database operations
python django_app\manage.py makemigrations
python django_app\manage.py migrate
python django_app\manage.py dbshell

# Create admin user
python django_app\manage.py createsuperuser

# Collect static files
python django_app\manage.py collectstatic

# Check for issues
python django_app\manage.py check

# Install new package
poetry add package-name
# or
pip install package-name
pip freeze > requirements.txt
```

## 🚦 Health Check

Run this PowerShell script to verify everything is working:

```powershell
# Save as check_health.ps1
Write-Host "Checking AI Pricing Agent Health..." -ForegroundColor Green

# Check Docker
if (docker ps | Select-String "pricing_postgres") {
    Write-Host "✓ PostgreSQL is running" -ForegroundColor Green
} else {
    Write-Host "✗ PostgreSQL is not running" -ForegroundColor Red
}

if (docker ps | Select-String "pricing_redis") {
    Write-Host "✓ Redis is running" -ForegroundColor Green
} else {
    Write-Host "✗ Redis is not running" -ForegroundColor Red
}

# Check Django
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000" -UseBasicParsing -TimeoutSec 5
    Write-Host "✓ Django is running" -ForegroundColor Green
} catch {
    Write-Host "✗ Django is not running" -ForegroundColor Red
}

# Check FastAPI
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/docs" -UseBasicParsing -TimeoutSec 5
    Write-Host "✓ FastAPI is running" -ForegroundColor Green
} catch {
    Write-Host "✗ FastAPI is not running" -ForegroundColor Red
}

Write-Host "`nSetup complete! Access the application at http://localhost:8000" -ForegroundColor Cyan
```

## 📚 Additional Resources

- **Django Documentation**: https://docs.djangoproject.com/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Docker Desktop for Windows**: https://docs.docker.com/desktop/windows/
- **WSL2 Documentation**: https://docs.microsoft.com/en-us/windows/wsl/

## 🆘 Getting Help

If you encounter issues:

1. Check the logs:
   - Django: Check terminal output
   - Docker: `docker logs <container-name>`
   - Application logs: Check `logs/app.log`

2. Common solutions:
   - Restart Docker Desktop
   - Delete `venv` folder and recreate
   - Clear browser cache
   - Check Windows Firewall settings

3. Contact support with:
   - Error messages
   - Output of `docker ps`
   - Python version: `python --version`
   - Windows version: `winver`

---

**Note**: This setup is for local development only. For production deployment, use the proper deployment guides with security hardening and performance optimization.