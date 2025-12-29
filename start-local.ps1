# AI Pricing Agent - Local Quick Start (PowerShell)
# Run with: powershell -ExecutionPolicy Bypass -File start-local.ps1

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AI Pricing Agent - Local Quick Start" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$DjangoPort = 8000
$FastApiPort = 8001
$PostgresPort = 5432
$RedisPort = 6379

# Function to check if port is in use
function Test-Port {
    param($Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $connection -ne $null
}

# Function to find available port
function Find-AvailablePort {
    param($StartPort)
    $port = $StartPort
    while (Test-Port $port) {
        $port++
    }
    return $port
}

# Check prerequisites
Write-Host "[1/4] Checking prerequisites..." -ForegroundColor Yellow
Write-Host ""

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH!" -ForegroundColor Red
    Write-Host "Please install Python 3.11+ from https://www.python.org/"
    Read-Host "Press Enter to exit"
    exit 1
}

# Check pip
try {
    $pipVersion = pip --version 2>&1 | Out-String
    Write-Host "[OK] pip found" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] pip is not installed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check and handle port conflicts
Write-Host ""
Write-Host "[2/4] Checking port availability..." -ForegroundColor Yellow
Write-Host ""

# Check Django port
if (Test-Port $DjangoPort) {
    Write-Host "[WARNING] Port $DjangoPort is in use!" -ForegroundColor Yellow
    $newPort = Find-AvailablePort ($DjangoPort + 1)
    Write-Host "Found available port: $newPort" -ForegroundColor Green

    $response = Read-Host "Use port $newPort for Django? (Y/N)"
    if ($response -eq 'Y' -or $response -eq 'y') {
        $DjangoPort = $newPort
    } else {
        $DjangoPort = Read-Host "Enter custom port for Django"
    }
}
Write-Host "[OK] Django will use port: $DjangoPort" -ForegroundColor Green

# Check FastAPI port
if (Test-Port $FastApiPort) {
    $FastApiPort = Find-AvailablePort ($FastApiPort + 1)
    Write-Host "[INFO] FastAPI will use port: $FastApiPort" -ForegroundColor Cyan
}

# Setup Python environment
Write-Host ""
Write-Host "[3/4] Setting up Python environment..." -ForegroundColor Yellow
Write-Host ""

# Check for virtual environment
$venvPath = ""
if (Test-Path "venv\Scripts\Activate.ps1") {
    $venvPath = "venv\Scripts\Activate.ps1"
    Write-Host "[INFO] Found virtual environment at venv\" -ForegroundColor Cyan
} elseif (Test-Path ".venv\Scripts\Activate.ps1") {
    $venvPath = ".venv\Scripts\Activate.ps1"
    Write-Host "[INFO] Found virtual environment at .venv\" -ForegroundColor Cyan
} else {
    Write-Host "[INFO] No virtual environment found" -ForegroundColor Yellow
    $createVenv = Read-Host "Create virtual environment? (Y/N)"
    if ($createVenv -eq 'Y' -or $createVenv -eq 'y') {
        Write-Host "Creating virtual environment..." -ForegroundColor Cyan
        python -m venv venv
        $venvPath = "venv\Scripts\Activate.ps1"
    }
}

# Activate virtual environment
if ($venvPath -ne "") {
    & $venvPath
    Write-Host "[OK] Virtual environment activated" -ForegroundColor Green
}

# Check Django installation
$djangoInstalled = pip show django 2>&1 | Out-String
if ($djangoInstalled -notmatch "Name: django") {
    Write-Host "[INFO] Installing Django..." -ForegroundColor Cyan
    pip install django
}

# Check for Docker (optional)
Write-Host ""
Write-Host "[INFO] Checking Docker services..." -ForegroundColor Cyan
$dockerAvailable = $false
try {
    docker version | Out-Null
    $dockerAvailable = $true
    Write-Host "[OK] Docker is available" -ForegroundColor Green

    $startDocker = Read-Host "Start database services in Docker? (Y/N)"
    if ($startDocker -eq 'Y' -or $startDocker -eq 'y') {
        Write-Host "Starting PostgreSQL and Redis..." -ForegroundColor Cyan

        if (Test-Path "docker-compose.windows.yml") {
            docker-compose -f docker-compose.windows.yml up -d postgres redis mailhog
        } else {
            Write-Host "[WARNING] docker-compose.windows.yml not found" -ForegroundColor Yellow
            Write-Host "Starting individual containers..." -ForegroundColor Cyan

            # Start PostgreSQL
            docker run -d --name pricing_postgres `
                -p ${PostgresPort}:5432 `
                -e POSTGRES_USER=pricing_user `
                -e POSTGRES_PASSWORD=pricing_password `
                -e POSTGRES_DB=pricing_agent `
                postgres:16-alpine 2>$null

            # Start Redis
            docker run -d --name pricing_redis `
                -p ${RedisPort}:6379 `
                redis:7-alpine 2>$null

            # Start MailHog
            docker run -d --name pricing_mailhog `
                -p 8025:8025 -p 1025:1025 `
                mailhog/mailhog 2>$null
        }

        Write-Host "Waiting for services to start..." -ForegroundColor Cyan
        Start-Sleep -Seconds 5
    }
} catch {
    Write-Host "[INFO] Docker not available - will use SQLite database" -ForegroundColor Yellow
}

# Start Django application
Write-Host ""
Write-Host "[4/4] Starting Django application..." -ForegroundColor Yellow
Write-Host ""

# Change to django_app directory
if (Test-Path "django_app") {
    Set-Location django_app

    # Run migrations if database is available
    if ($dockerAvailable) {
        Write-Host "Running database migrations..." -ForegroundColor Cyan
        python manage.py migrate --run-syncdb 2>$null
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  Django Development Server Starting" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Django URL: http://localhost:$DjangoPort" -ForegroundColor Cyan
    Write-Host "Admin URL:  http://localhost:$DjangoPort/admin" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Quick Links:" -ForegroundColor Yellow
    Write-Host "  Dashboard:  http://localhost:$DjangoPort" -ForegroundColor White
    Write-Host "  Analytics:  http://localhost:$DjangoPort/analytics/" -ForegroundColor White
    Write-Host "  Upload:     http://localhost:$DjangoPort/data-ingestion/upload/" -ForegroundColor White
    Write-Host ""
    Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
    Write-Host ""

    # Start Django server
    python manage.py runserver 0.0.0.0:$DjangoPort

    Set-Location ..
} else {
    Write-Host "[ERROR] django_app directory not found!" -ForegroundColor Red
    Write-Host "Current directory: $PWD" -ForegroundColor Red
    Write-Host "Please run this script from the project root." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Server stopped." -ForegroundColor Yellow
Read-Host "Press Enter to exit"