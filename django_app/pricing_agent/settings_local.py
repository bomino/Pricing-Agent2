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

print("Using LOCAL settings with SQLite database")