"""
Test settings for pricing_agent project.
"""
from .base import *
import tempfile
import os

# Override database to use in-memory SQLite for faster tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'OPTIONS': {
            'timeout': 20,
        },
    }
}

# Use dummy cache for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Disable migrations for faster test runs
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Test-specific settings
DEBUG = False
TESTING = True
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',  # Fast hasher for tests
]

# Disable logging during tests
LOGGING_CONFIG = None
LOGGING = {}

# Use test email backend
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Media files during testing
MEDIA_ROOT = tempfile.mkdtemp()

# Disable CSRF for API tests
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Test-specific middleware (remove some for faster tests)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.core.middleware.AuditMiddleware',
    'apps.core.middleware.OrganizationMiddleware',
]

# Celery test settings
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# FastAPI ML Service for tests (use test doubles)
ML_SERVICE_BASE_URL = 'http://testserver:8001'
ML_SERVICE_TIMEOUT = 5

# File upload limits for testing
FILE_UPLOAD_MAX_MEMORY_SIZE = 1048576  # 1MB for tests
DATA_UPLOAD_MAX_MEMORY_SIZE = 1048576  # 1MB for tests

# Security settings for tests
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False

# Redis settings for tests (use fakeredis if available)
try:
    import fakeredis
    CACHES['default'] = {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'connection_class': fakeredis.FakeConnection,
            },
        }
    }
except ImportError:
    # Fall back to dummy cache if fakeredis not available
    pass

# Test database routing
DATABASE_ROUTERS = []

# Static files for tests
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Disable template caching for tests
for template_engine in TEMPLATES:
    template_engine['OPTIONS']['debug'] = True
    if 'loaders' in template_engine['OPTIONS']:
        template_engine['OPTIONS']['loaders'] = [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]