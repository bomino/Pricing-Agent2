# Quick Start Guide - Local Testing

## Fastest Way to Test Locally

### Step 1: Install Dependencies (First Time Only)
```cmd
install-local.bat
```
This will:
- Create a virtual environment
- Install minimal Django dependencies
- Get you ready to run

### Step 2: Run Django
```cmd
test-django.bat
```
This is the simplest way to start Django on port 8000.

### Step 3: Access the Application
Open your browser to:
- Main App: http://localhost:8000
- Admin Panel: http://localhost:8000/admin
- Analytics: http://localhost:8000/analytics/
- Data Upload: http://localhost:8000/data-ingestion/upload/

## Alternative Scripts (If Port 8000 is Busy)

### Option A: Automatic Port Detection
```cmd
start-local.bat
```
This script will:
- Check if port 8000 is in use
- Offer to use alternative ports (8080, 8888)
- Let you kill the process using the port
- Optionally start Docker services

### Option B: PowerShell Version
```powershell
powershell -ExecutionPolicy Bypass -File start-local.ps1
```
Features:
- Better port detection
- Automatically finds next available port
- Cleaner output with colors

## Troubleshooting

### "Port 8000 is already in use"

#### Find what's using the port:
```cmd
netstat -ano | findstr :8000
```

#### Kill the process (replace PID with actual number):
```cmd
taskkill /F /PID [PID]
```

#### Or use a different port:
```cmd
cd django_app
python manage.py runserver 8080
```

### "Module not found" Errors

Run the installation script:
```cmd
install-local.bat
```

Or manually install requirements:
```cmd
pip install -r requirements-simple.txt
```

### "Python not found"

1. Install Python 3.11+ from https://www.python.org/
2. **Important**: Check "Add Python to PATH" during installation
3. Restart your command prompt

### Database Errors

For local testing without Docker, Django will use SQLite by default.

If you want to use PostgreSQL:
1. Install Docker Desktop
2. Run: `docker-compose -f docker-compose.windows.yml up -d`
3. Then run Django normally

## Quick Commands Reference

| Task | Command |
|------|---------|
| Install dependencies | `install-local.bat` |
| Start Django (simple) | `test-django.bat` |
| Start Django (smart) | `start-local.bat` |
| Start with PowerShell | `powershell -ExecutionPolicy Bypass -File start-local.ps1` |
| Stop all services | `stop-windows.bat` |
| Check ports | `netstat -ano \| findstr :8000` |

## Minimal Testing (No Installation)

If you just want to test if Django works:
```cmd
cd django_app
python manage.py runserver
```

If that works, you're good to go!

## Default Credentials

If you create a superuser, you can use:
- Username: admin
- Password: (whatever you set)

To create a superuser:
```cmd
cd django_app
python manage.py createsuperuser
```

## Need Full Features?

For the complete setup with Docker, PostgreSQL, Redis, and all services:
```cmd
start-windows.bat
```

This will guide you through the full installation and setup process.