# Quick Django Commands for Local Development

## Essential Commands (Copy & Paste)

### 1. Apply Migrations (Run this first!)
```bash
cd django_app
python manage.py migrate --settings=pricing_agent.settings_local
```

### 2. Create Superuser Account
```bash
cd django_app
python manage.py createsuperuser --settings=pricing_agent.settings_local
```

### 3. Run Development Server
```bash
cd django_app
python manage.py runserver --settings=pricing_agent.settings_local
```

### 4. Quick One-Liner to Start Everything
```bash
cd django_app && python manage.py migrate --settings=pricing_agent.settings_local && python manage.py runserver --settings=pricing_agent.settings_local
```

## Batch Files Available

| File | Purpose |
|------|---------|
| **run-local-dev.bat** | Complete setup with migrations, superuser check, and server start |
| **apply-migrations.bat** | Just apply database migrations |
| **run-sqlite.bat** | Quick server start with SQLite (basic) |
| **test-django-now.bat** | Test if Django configuration is correct |

## Common Issues & Solutions

### "You have X unapplied migration(s)"
```bash
python manage.py migrate --settings=pricing_agent.settings_local
```

### "django.db.utils.OperationalError: connection to PostgreSQL"
You forgot the `--settings` flag! Always add:
```bash
--settings=pricing_agent.settings_local
```

### "No such table: xxx"
Run migrations first:
```bash
python manage.py migrate --settings=pricing_agent.settings_local --run-syncdb
```

### Create Sample Data
```bash
cd django_app
python manage.py create_sample_procurement_data --settings=pricing_agent.settings_local
```

## URLs After Server Starts

- **Main App**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **Login**: http://localhost:8000/accounts/login/
- **Data Upload**: http://localhost:8000/data-ingestion/upload/
- **Analytics**: http://localhost:8000/analytics/

## PowerShell Commands (Alternative)

### Set Environment Variable & Run
```powershell
$env:DJANGO_SETTINGS_MODULE = "pricing_agent.settings_local"
cd django_app
python manage.py migrate
python manage.py runserver
```

## Tips

1. **Always use `--settings=pricing_agent.settings_local`** for local development
2. The SQLite database file will be at `django_app/db.sqlite3`
3. No Docker or PostgreSQL needed for local testing
4. Default superuser credentials you set will work for admin panel
5. Sample data can be created after migrations are applied

## Quick Test After Setup

1. Run migrations: `apply-migrations.bat`
2. Start server: `run-local-dev.bat`
3. Open browser: http://localhost:8000
4. Login at: http://localhost:8000/accounts/login/
5. Upload data at: http://localhost:8000/data-ingestion/upload/