# ========================================
# AI Pricing Agent - Windows Setup Script
# ========================================
# Run this script once to set up the development environment
# Execute in PowerShell as Administrator

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "AI Pricing Agent - Initial Setup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if a command exists
function Test-Command {
    param($Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

$missing = @()

# Check Python
if (Test-Command python) {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python found: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "[X] Python not found" -ForegroundColor Red
    $missing += "Python"
}

# Check Docker
if (Test-Command docker) {
    Write-Host "[OK] Docker found" -ForegroundColor Green
} else {
    Write-Host "[X] Docker not found" -ForegroundColor Red
    $missing += "Docker Desktop"
}

# Check Git
if (Test-Command git) {
    Write-Host "[OK] Git found" -ForegroundColor Green
} else {
    Write-Host "[X] Git not found" -ForegroundColor Red
    $missing += "Git"
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing prerequisites: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Please install the missing software and run this script again." -ForegroundColor Red
    Write-Host ""
    Write-Host "Download links:" -ForegroundColor Yellow
    Write-Host "- Python: https://www.python.org/downloads/" -ForegroundColor Cyan
    Write-Host "- Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Cyan
    Write-Host "- Git: https://git-scm.com/download/win" -ForegroundColor Cyan
    exit 1
}

Write-Host ""
Write-Host "All prerequisites found!" -ForegroundColor Green
Write-Host ""

# Create necessary directories
Write-Host "Creating project directories..." -ForegroundColor Yellow
$directories = @(
    "media",
    "static", 
    "logs",
    "django_app\static",
    "django_app\media",
    "django_app\templates",
    "fastapi_ml\ml_artifacts\models",
    "backups"
)

foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "[OK] Created $dir" -ForegroundColor Green
    } else {
        Write-Host "[-] $dir already exists" -ForegroundColor Gray
    }
}

Write-Host ""

# Copy environment file if not exists
if (!(Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "[OK] Created .env from template" -ForegroundColor Green
        Write-Host "    Please edit .env with your configuration" -ForegroundColor Yellow
    } else {
        Write-Host "[X] .env.example not found" -ForegroundColor Red
    }
} else {
    Write-Host "[-] .env already exists" -ForegroundColor Gray
}

Write-Host ""

# Install Python dependencies
Write-Host "Setting up Python environment..." -ForegroundColor Yellow

# Check if venv exists
if (!(Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "[-] Virtual environment already exists" -ForegroundColor Gray
}

# Activate venv and install packages
Write-Host "Installing Python packages..." -ForegroundColor Cyan
& ".\venv\Scripts\pip.exe" install --upgrade pip | Out-Null
& ".\venv\Scripts\pip.exe" install wheel setuptools | Out-Null

# Check which requirements file to use
$requirementsFile = ""
if (Test-Path "requirements-simple.txt") {
    $requirementsFile = "requirements-simple.txt"
    Write-Host "Using simplified requirements (recommended for first setup)..." -ForegroundColor Cyan
} elseif (Test-Path "requirements\development.txt") {
    $requirementsFile = "requirements\development.txt"
    Write-Host "Using development requirements..." -ForegroundColor Cyan
} elseif (Test-Path "requirements.txt") {
    $requirementsFile = "requirements.txt"
    Write-Host "Using main requirements.txt..." -ForegroundColor Cyan
} elseif (Test-Path "pyproject.toml") {
    Write-Host "Using Poetry for dependency management..." -ForegroundColor Cyan
    & ".\venv\Scripts\pip.exe" install poetry
    & ".\venv\Scripts\poetry.exe" install
    Write-Host "[OK] Python packages installed via Poetry" -ForegroundColor Green
} else {
    Write-Host "[X] No requirements file found" -ForegroundColor Red
    Write-Host "Creating basic requirements..." -ForegroundColor Yellow
    $requirementsFile = "requirements.txt"
}

if ($requirementsFile -ne "") {
    & ".\venv\Scripts\pip.exe" install -r $requirementsFile
    Write-Host "[OK] Python packages installed from $requirementsFile" -ForegroundColor Green
}

Write-Host ""

# Start Docker containers
Write-Host "Setting up Docker containers..." -ForegroundColor Yellow

# Check if Docker is running
docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop is not running. Please start it and press Enter to continue..." -ForegroundColor Yellow
    Read-Host
}

# Check if docker-compose.windows.yml exists
if (!(Test-Path "docker-compose.windows.yml")) {
    Write-Host "Creating docker-compose.windows.yml..." -ForegroundColor Cyan
    $dockerComposeContent = @'
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
      - "1025:1025"
      - "8025:8025"
    
volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
'@
    $dockerComposeContent | Out-File -FilePath "docker-compose.windows.yml" -Encoding UTF8
    Write-Host "[OK] docker-compose.windows.yml created" -ForegroundColor Green
}

Write-Host "Starting Docker containers..." -ForegroundColor Cyan
docker-compose -f docker-compose.windows.yml up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Docker containers started" -ForegroundColor Green
} else {
    Write-Host "[X] Failed to start Docker containers" -ForegroundColor Red
    exit 1
}

# Wait for PostgreSQL to be ready
Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Cyan
$maxAttempts = 30
$attempt = 0
while ($attempt -lt $maxAttempts) {
    docker exec pricing_postgres pg_isready -U pricing_user 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] PostgreSQL is ready" -ForegroundColor Green
        break
    }
    Start-Sleep -Seconds 2
    $attempt++
}

if ($attempt -eq $maxAttempts) {
    Write-Host "[X] PostgreSQL failed to start" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Create TimescaleDB extension
Write-Host "Setting up TimescaleDB..." -ForegroundColor Yellow
docker exec pricing_postgres psql -U pricing_user -d pricing_agent -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" 2>&1 | Out-Null
Write-Host "[OK] TimescaleDB extension created" -ForegroundColor Green

Write-Host ""

# Run Django migrations
Write-Host "Setting up Django database..." -ForegroundColor Yellow

if (Test-Path "django_app\manage.py") {
    Set-Location django_app
    & "..\venv\Scripts\python.exe" manage.py makemigrations 2>&1 | Out-Null
    & "..\venv\Scripts\python.exe" manage.py migrate 2>&1 | Out-Null
    Write-Host "[OK] Database migrations completed" -ForegroundColor Green
    
    # Check if superuser exists
    Write-Host ""
    $createSuperuser = Read-Host "Do you want to create a Django superuser? (y/n)"
    if ($createSuperuser -eq 'y') {
        & "..\venv\Scripts\python.exe" manage.py createsuperuser
    }
    
    Set-Location ..
} else {
    Write-Host "[!] Django app not found. Skipping migrations." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Setup completed successfully!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit the .env file with your configuration" -ForegroundColor White
Write-Host "2. Run 'start-windows.bat' to start all services" -ForegroundColor White
Write-Host "3. Access the application at http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "- Django App: http://localhost:8000" -ForegroundColor White
Write-Host "- Django Admin: http://localhost:8000/admin" -ForegroundColor White
Write-Host "- FastAPI Docs: http://localhost:8001/docs" -ForegroundColor White
Write-Host "- MailHog: http://localhost:8025" -ForegroundColor White
Write-Host ""
Write-Host "To start services: run 'start-windows.bat'" -ForegroundColor Yellow
Write-Host "To stop services: run 'stop-windows.bat'" -ForegroundColor Yellow
Write-Host ""