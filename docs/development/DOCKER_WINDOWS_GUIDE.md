# Docker Setup Guide for Windows

## Why Docker?

Docker provides:
- **Consistency**: Same environment for all developers
- **Isolation**: No conflicts with other projects
- **Complete Stack**: PostgreSQL, Redis, Django, Celery all configured
- **Production-like**: Matches deployment environment
- **Easy Setup**: One command to start everything

## Prerequisites

### 1. Install Docker Desktop
- Download from: https://www.docker.com/products/docker-desktop
- Choose **WSL 2 backend** during installation (recommended)
- Requires Windows 10/11 Pro, Enterprise, or Education

### 2. System Requirements
- 4GB RAM minimum (8GB recommended)
- WSL 2 enabled (Docker Desktop will guide you)
- Virtualization enabled in BIOS

### 3. Verify Installation
```cmd
docker --version
docker-compose --version
```

## Quick Start

### Start Everything
```cmd
docker-start.bat
```
This will:
1. Check Docker is running
2. Build images if needed
3. Start all services
4. Run migrations
5. Prompt for superuser creation

### Stop Everything
```cmd
docker-stop.bat
```

## Docker Commands Reference

### Service Management
```bash
# Start all services
docker-compose -f docker-compose.simple.yml up -d

# Stop all services
docker-compose -f docker-compose.simple.yml down

# View running containers
docker ps

# View logs
docker-compose -f docker-compose.simple.yml logs -f django
docker-compose -f docker-compose.simple.yml logs -f postgres

# Restart a service
docker-compose -f docker-compose.simple.yml restart django
```

### Django Management
```bash
# Run migrations
docker exec pricing_django python manage.py migrate

# Create superuser
docker exec -it pricing_django python manage.py createsuperuser

# Django shell
docker exec -it pricing_django python manage.py shell

# Run Django commands
docker exec pricing_django python manage.py <command>

# Create sample data
docker exec pricing_django python manage.py create_sample_procurement_data
```

### Database Access
```bash
# PostgreSQL shell
docker exec -it pricing_postgres psql -U pricing_user -d pricing_agent

# Backup database
docker exec pricing_postgres pg_dump -U pricing_user pricing_agent > backup.sql

# Restore database
docker exec -i pricing_postgres psql -U pricing_user pricing_agent < backup.sql
```

### Debugging
```bash
# View container logs
docker logs pricing_django
docker logs pricing_postgres

# Enter container shell
docker exec -it pricing_django /bin/bash
docker exec -it pricing_postgres /bin/bash

# Check container health
docker ps --format "table {{.Names}}\t{{.Status}}"

# Inspect container
docker inspect pricing_django
```

## Troubleshooting

### Docker Desktop Not Starting
1. **Enable virtualization in BIOS**
   - Restart computer
   - Enter BIOS (usually F2, F10, or DEL key)
   - Enable Intel VT-x or AMD-V

2. **Enable WSL 2**
   ```powershell
   # Run as Administrator
   wsl --install
   wsl --set-default-version 2
   ```

3. **Windows Features**
   - Enable "Windows Subsystem for Linux"
   - Enable "Virtual Machine Platform"
   - Enable "Hyper-V" (Windows Pro only)

### Port Already in Use
```cmd
# Check what's using port 8000
netstat -ano | findstr :8000

# Kill process using PID
taskkill /PID <PID> /F
```

### Container Won't Start
```bash
# Remove all containers and start fresh
docker-compose -f docker-compose.simple.yml down -v
docker-compose -f docker-compose.simple.yml up -d --build
```

### Database Connection Issues
```bash
# Check PostgreSQL is running
docker ps | findstr postgres

# Test connection
docker exec pricing_postgres pg_isready -U pricing_user

# View PostgreSQL logs
docker logs pricing_postgres
```

### Permission Issues on Windows
- Run Docker Desktop as Administrator
- Ensure your user is in the "docker-users" group
- Restart Docker Desktop after permission changes

### Slow Performance
1. **Allocate more resources**:
   - Docker Desktop → Settings → Resources
   - Increase CPU and Memory limits

2. **Use WSL 2 backend** (faster than Hyper-V)

3. **Exclude from antivirus**:
   - Add Docker folders to Windows Defender exclusions
   - Exclude: `C:\ProgramData\DockerDesktop`

## Docker vs Local Development

### When to Use Docker
✅ Team development (consistency)
✅ Testing production-like environment
✅ Need PostgreSQL, Redis, Celery
✅ Deploying to production
✅ Complex dependencies

### When to Use Local (SQLite)
✅ Quick prototyping
✅ Limited system resources
✅ Simple testing
✅ Learning Django basics
✅ Offline development

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Django | http://localhost:8000 | Main application |
| Admin | http://localhost:8000/admin | Django admin panel |
| MailHog | http://localhost:8025 | Email testing UI |
| PostgreSQL | localhost:5432 | Database |
| Redis | localhost:6379 | Cache & queues |

## Database Credentials

- **Host**: localhost (from host) or postgres (from containers)
- **Port**: 5432
- **Database**: pricing_agent
- **Username**: pricing_user
- **Password**: pricing_password

## Best Practices

1. **Always use docker-compose commands** instead of docker directly
2. **Check logs** when something doesn't work
3. **Don't modify container files directly** - they're temporary
4. **Use volumes** for persistent data
5. **Rebuild when requirements change**: `docker-compose build --no-cache`

## Advanced Usage

### Production Mode
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Development with Live Reload
The current setup mounts `./django_app` as a volume, so code changes are reflected immediately.

### Running Tests
```bash
docker exec pricing_django python manage.py test
```

### Scaling Services
```bash
docker-compose -f docker-compose.simple.yml up -d --scale celery=3
```

## Comparison: Docker vs Local

| Aspect | Docker | Local (SQLite) |
|--------|--------|----------------|
| Setup Time | 5-10 minutes | 2 minutes |
| Database | PostgreSQL | SQLite |
| Cache | Redis | In-memory |
| Email Testing | MailHog | Console |
| Background Tasks | Celery | None |
| Resource Usage | Higher | Lower |
| Production-like | Yes | No |
| Team Consistency | High | Low |

## Next Steps

1. Run `docker-start.bat` to begin
2. Create a superuser when prompted
3. Access http://localhost:8000
4. Upload test data
5. Explore the analytics dashboard

Remember: Docker might seem complex initially, but it ensures everyone on your team has the exact same development environment, eliminating "works on my machine" issues!