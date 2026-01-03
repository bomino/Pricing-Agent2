"""
Local settings for development without Docker/PostgreSQL
Uses SQLite for quick testing
"""

from .settings import *

# Override database to use SQLite for local testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Disable debug toolbar if it causes issues
if 'debug_toolbar' in INSTALLED_APPS:
    INSTALLED_APPS.remove('debug_toolbar')
if 'debug_toolbar.middleware.DebugToolbarMiddleware' in MIDDLEWARE:
    MIDDLEWARE.remove('debug_toolbar.middleware.DebugToolbarMiddleware')

# Simplified email backend for local testing
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Allow all hosts for local testing
ALLOWED_HOSTS = ['*']

# Disable CSRF for local testing (optional)
# CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000']

# Use local memory cache instead of Redis for local testing
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Disable Celery for local testing
CELERY_TASK_ALWAYS_EAGER = True

# Disable ML anomaly detection during local testing (no ML service running)
ML_ANOMALY_DETECTION_ENABLED = False

print("Using LOCAL settings with SQLite database")