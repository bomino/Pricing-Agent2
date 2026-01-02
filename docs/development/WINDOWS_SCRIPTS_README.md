# Windows Batch Scripts Documentation

## Overview

This project includes two Windows batch scripts to simplify development setup and management on Windows systems.

## Scripts

### start-windows.bat

An interactive startup script that handles the complete development environment setup.

#### Features

1. **Prerequisites Verification**
   - Checks for Python installation
   - Verifies pip availability
   - Ensures Docker Desktop is running
   - Checks port availability (8000, 8001, 5432, 6379)

2. **Flexible Configuration**
   - Option 1: Windows Development Mode
     - Runs PostgreSQL, Redis, and MailHog in Docker
     - Django and FastAPI run locally
     - Ideal for development and debugging
   - Option 2: Full Docker Mode
     - All services run in Docker containers
     - Better isolation and consistency
     - Closer to production environment

3. **Automatic Setup**
   - Virtual environment detection and creation
   - Python dependencies installation
   - Database migrations
   - Static files collection
   - Superuser account creation (optional)
   - Celery workers startup (optional)

4. **User-Friendly Output**
   - Color-coded messages (green for success)
   - Clear status indicators
   - Service URLs and quick access links
   - Error handling with helpful messages

#### Usage

```cmd
# Run from project root directory
start-windows.bat
```

Follow the interactive prompts to:
1. Choose between Windows development or full Docker setup
2. Optionally create a virtual environment
3. Optionally create a superuser account
4. Optionally start Celery workers

### stop-windows.bat

A comprehensive shutdown script that properly stops all services and cleans up resources.

#### Features

1. **Process Management**
   - Stops Django server
   - Stops FastAPI ML service
   - Stops Celery workers and beat
   - Optional cleanup of all Python processes

2. **Docker Container Management**
   - Automatically detects which docker-compose configuration is in use
   - Stops containers from both docker-compose.windows.yml and docker-compose.simple.yml
   - Cleans up orphaned containers
   - Removes volumes for clean restart

3. **Port Status Verification**
   - Checks if ports are successfully freed
   - Warns about ports still in use
   - Helps identify stuck processes

4. **Optional Cleanup**
   - Python __pycache__ directories
   - Django static files cache
   - Old log files (preserves latest)
   - Temporary files

#### Usage

```cmd
# Run from project root directory
stop-windows.bat
```

The script will:
1. Stop all application processes
2. Stop Docker containers
3. Check port availability
4. Optionally clean temporary files

## Troubleshooting

### Common Issues

1. **"Docker Desktop is not running"**
   - Start Docker Desktop manually
   - The script will attempt to start it automatically
   - Wait for Docker to fully initialize before running again

2. **"Port 8000 is already in use"**
   - Run stop-windows.bat first
   - Check Task Manager for python.exe processes
   - Use `netstat -ano | findstr :8000` to find the process

3. **"Python is not installed or not in PATH"**
   - Install Python 3.11+ from https://www.python.org/
   - Ensure "Add Python to PATH" is checked during installation
   - Restart command prompt after installation

4. **"Failed to start Docker containers"**
   - Check Docker Desktop is running
   - Verify docker-compose files exist
   - Check for disk space issues
   - Review Docker logs: `docker-compose logs`

### Manual Cleanup

If scripts fail to clean up properly:

```cmd
# Stop all Python processes
taskkill /IM python.exe /F

# Stop all Docker containers
docker stop $(docker ps -a -q)
docker rm $(docker ps -a -q)

# Clean Docker volumes
docker volume prune -f
```

## Requirements

- Windows 10/11 (Professional or Enterprise for Docker Desktop)
- Python 3.11+ with pip
- Docker Desktop for Windows
- Git Bash or Command Prompt
- Administrator privileges (for some operations)

## Environment Variables

The scripts respect the following environment variables if set:

- `COMPOSE_FILE` - Override default docker-compose file
- `PYTHONPATH` - Python installation path
- `VIRTUAL_ENV` - Active virtual environment path

## Integration with IDE

### Visual Studio Code

Add to `.vscode/tasks.json`:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Start Pricing Agent",
            "type": "shell",
            "command": "${workspaceFolder}/start-windows.bat",
            "problemMatcher": []
        },
        {
            "label": "Stop Pricing Agent",
            "type": "shell",
            "command": "${workspaceFolder}/stop-windows.bat",
            "problemMatcher": []
        }
    ]
}
```

Then use `Ctrl+Shift+P` → "Tasks: Run Task" to execute.

### PyCharm

1. Go to Run → Edit Configurations
2. Add new Shell Script configuration
3. Set Script path to `start-windows.bat` or `stop-windows.bat`
4. Set Working directory to project root

## Best Practices

1. Always run `stop-windows.bat` before shutting down your development machine
2. Use Windows Development mode for active development and debugging
3. Use Full Docker mode for testing production-like behavior
4. Regularly clean temporary files to free disk space
5. Keep Docker Desktop updated for best performance

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs in the `logs/` directory
3. Check Docker logs: `docker-compose logs`
4. Consult the main documentation in CLAUDE.md