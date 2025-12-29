"""
Security Settings for AI Pricing Agent
Enhanced security configuration with enterprise-grade controls
"""
import os
from datetime import timedelta
from .base import *

# =============================================================================
# ENTERPRISE SECURITY CONFIGURATION
# =============================================================================

# Security Middleware (Order is important!)
MIDDLEWARE = [
    'apps.core.security_middleware.SecurityHeadersMiddleware',
    'apps.core.security_middleware.ThreatDetectionMiddleware', 
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.security_middleware.EnhancedAuditMiddleware',
    'apps.core.middleware.OrganizationMiddleware',
    'apps.core.security_middleware.ComplianceMiddleware',
    'apps.core.middleware.ErrorHandlingMiddleware',
    'apps.core.middleware.PerformanceMiddleware',
    'apps.core.security_middleware.DataEncryptionMiddleware',
]

# Authentication Configuration
AUTHENTICATION_BACKENDS = [
    'apps.core.enterprise_auth.OAuth2Authentication',
    'apps.core.enterprise_auth.APIKeyAuthentication', 
    'apps.core.enterprise_auth.EnhancedMLServiceAuthentication',
    'django.contrib.auth.backends.ModelBackend',
]

# Django REST Framework Security
REST_FRAMEWORK.update({
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.core.enterprise_auth.EnterpriseJWTAuthentication',
        'apps.core.enterprise_auth.APIKeyAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour', 
        'ml_predict': '60/minute',
        'bulk_operations': '10/hour',
        'auth': '20/hour',
        'password_reset': '5/hour',
        'mfa_verification': '10/minute',
    },
    'DEFAULT_CONTENT_NEGOTIATION_CLASS': 'rest_framework.content_negotiation.DefaultContentNegotiation',
    'DEFAULT_METADATA_CLASS': 'rest_framework.metadata.SimpleMetadata',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
})

# =============================================================================
# SECURITY HEADERS AND PROTECTION
# =============================================================================

# Security Headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Frame Options
X_FRAME_OPTIONS = 'DENY'

# SSL/HTTPS Settings
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Content Security Policy
CSP_DEFAULT_SRC = ["'self'"]
CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net"]
CSP_STYLE_SRC = ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"]
CSP_FONT_SRC = ["'self'", "https://fonts.gstatic.com"]
CSP_IMG_SRC = ["'self'", "data:", "blob:", "https:"]
CSP_CONNECT_SRC = ["'self'", "wss:", "ws:"]
CSP_FRAME_ANCESTORS = ["'none'"]
CSP_BASE_URI = ["'self'"]
CSP_FORM_ACTION = ["'self'"]

if not DEBUG:
    CSP_UPGRADE_INSECURE_REQUESTS = True
    CSP_BLOCK_ALL_MIXED_CONTENT = True

# Permissions Policy
PERMISSIONS_POLICY = {
    'camera': '()',
    'microphone': '()',
    'geolocation': '()',
    'usb': '()',
    'bluetooth': '()',
    'magnetometer': '()',
    'accelerometer': '()',
    'gyroscope': '()',
    'payment': '(self)',
}

# =============================================================================
# SESSION AND COOKIE SECURITY
# =============================================================================

# Session Security
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 7200  # 2 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# CSRF Protection
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = True
CSRF_COOKIE_AGE = 3600  # 1 hour

# Cookie Security
LANGUAGE_COOKIE_SECURE = not DEBUG
LANGUAGE_COOKIE_HTTPONLY = True
LANGUAGE_COOKIE_SAMESITE = 'Lax'

# =============================================================================
# PASSWORD AND AUTHENTICATION SECURITY
# =============================================================================

# Enhanced Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'apps.core.validators.EnterprisePasswordValidator',
    },
]

# Password Hashing
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',  # Most secure
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',  # Default fallback
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# =============================================================================
# ENCRYPTION AND CRYPTOGRAPHY
# =============================================================================

# Master encryption key (should be stored in secure key management)
ENCRYPTION_MASTER_KEY = env('ENCRYPTION_MASTER_KEY', default=SECRET_KEY)

# RSA Keys for JWT (should be generated and stored securely)
RSA_PRIVATE_KEY = env('RSA_PRIVATE_KEY', default='')
RSA_PUBLIC_KEY = env('RSA_PUBLIC_KEY', default='')

# Field-level encryption settings
FIELD_ENCRYPTION_ENABLED = True
FIELD_ENCRYPTION_ALGORITHM = 'AES-256-GCM'

# =============================================================================
# HASHICORP VAULT INTEGRATION
# =============================================================================

VAULT_SETTINGS = {
    'URL': env('VAULT_ADDR', default='http://localhost:8200'),
    'TOKEN': env('VAULT_TOKEN', default=''),
    'ROLE_ID': env('VAULT_ROLE_ID', default=''),
    'SECRET_ID': env('VAULT_SECRET_ID', default=''),
    'MOUNT_POINT': env('VAULT_MOUNT_POINT', default='secret'),
    'CA_CERT_PATH': env('VAULT_CACERT', default=''),
    'CLIENT_CERT_PATH': env('VAULT_CLIENT_CERT', default=''),
    'CLIENT_KEY_PATH': env('VAULT_CLIENT_KEY', default=''),
    'VERIFY_SSL': env('VAULT_VERIFY_SSL', default=True),
    'TIMEOUT': env('VAULT_TIMEOUT', default=30),
    'MAX_RETRIES': env('VAULT_MAX_RETRIES', default=3),
}

# =============================================================================
# MULTI-FACTOR AUTHENTICATION
# =============================================================================

# MFA Settings
MFA_ENABLED = True
MFA_TOTP_ISSUER = 'AI Pricing Agent'
MFA_BACKUP_CODES_COUNT = 10
MFA_REQUIRED_ROLES = ['admin', 'manager', 'owner']

# TOTP Settings
TOTP_WINDOW = 1  # Number of time periods to check
TOTP_PERIOD = 30  # Time period in seconds
TOTP_ALGORITHM = 'SHA1'
TOTP_DIGITS = 6

# =============================================================================
# RATE LIMITING AND DDoS PROTECTION
# =============================================================================

# Rate Limiting Configuration
RATE_LIMIT_ENABLED = True

# Cache backend for rate limiting
CACHES.update({
    'rate_limit': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL') + '/1',  # Use DB 1 for rate limiting
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
})

# Rate limiting rules
RATE_LIMIT_RULES = {
    'global': {'rate': '1000/hour', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
    'auth': {'rate': '20/hour', 'methods': ['POST']},
    'api': {'rate': '500/hour', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
    'ml_predict': {'rate': '60/minute', 'methods': ['POST']},
    'file_upload': {'rate': '50/hour', 'methods': ['POST']},
}

# =============================================================================
# AUDIT LOGGING AND MONITORING
# =============================================================================

# Enhanced Logging Configuration
LOGGING.update({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {
            'format': '{asctime} [{levelname}] {name}: {message} - User: {user} - IP: {ip} - Request: {request_id}',
            'style': '{',
        },
        'audit': {
            'format': '{asctime} [AUDIT] {name}: {message}',
            'style': '{',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'filters': {
        'security_filter': {
            '()': 'apps.core.logging_filters.SecurityFilter',
        },
        'audit_filter': {
            '()': 'apps.core.logging_filters.AuditFilter', 
        },
    },
    'handlers': {
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 10,
            'formatter': 'security',
            'filters': ['security_filter'],
        },
        'audit_file': {
            'level': 'INFO', 
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'audit.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 10,
            'formatter': 'audit',
            'filters': ['audit_filter'],
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'siem': {
            'level': 'WARNING',
            'class': 'apps.core.logging_handlers.SIEMHandler',
            'endpoint': env('SIEM_ENDPOINT', default=''),
            'api_key': env('SIEM_API_KEY', default=''),
        },
    },
    'loggers': {
        'django.security': {
            'handlers': ['security_file', 'console', 'siem'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.core.security': {
            'handlers': ['security_file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.core.audit': {
            'handlers': ['audit_file', 'siem'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['security_file', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
})

# =============================================================================
# DATA CLASSIFICATION AND PROTECTION
# =============================================================================

# Data Classification Levels
DATA_CLASSIFICATION_LEVELS = [
    ('public', 'Public'),
    ('internal', 'Internal'), 
    ('confidential', 'Confidential'),
    ('restricted', 'Restricted'),
    ('top_secret', 'Top Secret'),
]

# Sensitive Data Patterns (for DLP)
SENSITIVE_DATA_PATTERNS = {
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card': r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'phone': r'\b\+?1?\d{9,15}\b',
    'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
}

# =============================================================================
# COMPLIANCE CONFIGURATION
# =============================================================================

# GDPR Settings
GDPR_COMPLIANCE = {
    'ENABLED': True,
    'CONTROLLER_NAME': env('GDPR_CONTROLLER_NAME', default=''),
    'CONTROLLER_ADDRESS': env('GDPR_CONTROLLER_ADDRESS', default=''),
    'DPO_CONTACT': env('GDPR_DPO_CONTACT', default=''),
    'CONSENT_RENEWAL_DAYS': 365,
    'DATA_RETENTION_DAYS': 2555,  # 7 years
    'BREACH_NOTIFICATION_HOURS': 72,
}

# CCPA Settings  
CCPA_COMPLIANCE = {
    'ENABLED': True,
    'BUSINESS_NAME': env('CCPA_BUSINESS_NAME', default=''),
    'CONTACT_EMAIL': env('CCPA_CONTACT_EMAIL', default=''),
    'PRIVACY_POLICY_URL': env('CCPA_PRIVACY_POLICY_URL', default=''),
    'OPT_OUT_URL': env('CCPA_OPT_OUT_URL', default=''),
}

# SOC 2 Settings
SOC2_COMPLIANCE = {
    'ENABLED': True,
    'SERVICE_ORGANIZATION': env('SOC2_SERVICE_ORG', default=''),
    'AUDIT_FIRM': env('SOC2_AUDIT_FIRM', default=''),
    'AUDIT_PERIOD_START': env('SOC2_AUDIT_START', default=''),
    'AUDIT_PERIOD_END': env('SOC2_AUDIT_END', default=''),
}

# Geographic Restrictions
RESTRICTED_COUNTRIES = env('RESTRICTED_COUNTRIES', default=[])

# =============================================================================
# FILE UPLOAD AND MEDIA SECURITY
# =============================================================================

# File Upload Security
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Allowed File Types
ALLOWED_FILE_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', 
    '.csv', '.txt', '.zip', '.png', '.jpg', '.jpeg'
]

# File Scanning
FILE_SCANNING_ENABLED = True
FILE_SCANNING_API_KEY = env('FILE_SCANNING_API_KEY', default='')

# Media File Security
SECURE_FILE_STORAGE = True
FILE_ENCRYPTION_ENABLED = True

# =============================================================================
# API SECURITY
# =============================================================================

# API Security Headers
API_SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY', 
    'X-XSS-Protection': '1; mode=block',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin',
}

# API Key Settings
API_KEY_LENGTH = 32
API_KEY_PREFIX = 'pa_'  # Pricing Agent prefix
API_KEY_EXPIRY_DAYS = 365
API_KEY_RATE_LIMIT = '5000/hour'

# JWT Settings
JWT_ALGORITHM = 'RS256'  # RSA signature
JWT_EXPIRY_MINUTES = 60
JWT_REFRESH_EXPIRY_HOURS = 24
JWT_ISSUER = 'pricing-agent'
JWT_AUDIENCE = 'pricing-agent-api'

# =============================================================================
# DATABASE SECURITY
# =============================================================================

# Database Connection Security
DATABASES['default'].update({
    'OPTIONS': {
        'sslmode': 'require' if not DEBUG else 'prefer',
        'options': '-c default_transaction_isolation=serializable'
    },
    'CONN_MAX_AGE': 300,  # 5 minutes
})

# Database Query Security
DATABASE_QUERY_TIMEOUT = 30  # 30 seconds
DATABASE_SLOW_QUERY_THRESHOLD = 5  # 5 seconds

# =============================================================================
# NETWORK AND INFRASTRUCTURE SECURITY
# =============================================================================

# Allowed Hosts (should be specific in production)
if not DEBUG:
    ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])
else:
    ALLOWED_HOSTS = ['*']

# CORS Configuration (restrictive in production)
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-organization-id',
]

# Trusted Proxy Configuration
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# =============================================================================
# INCIDENT RESPONSE AND ALERTING
# =============================================================================

# Incident Response Settings
INCIDENT_RESPONSE_ENABLED = True
INCIDENT_EMAIL = env('INCIDENT_EMAIL', default='')
SECURITY_TEAM_EMAIL = env('SECURITY_TEAM_EMAIL', default='')

# Security Alerting
SECURITY_ALERTS = {
    'FAILED_LOGIN_THRESHOLD': 5,
    'SUSPICIOUS_IP_THRESHOLD': 10,
    'RATE_LIMIT_ALERT_THRESHOLD': 100,
    'ERROR_RATE_THRESHOLD': 0.05,  # 5%
}

# Breach Notification Settings
BREACH_NOTIFICATION = {
    'ENABLED': True,
    'AUTO_NOTIFICATION_THRESHOLD': 'high',  # critical, high, medium, low
    'NOTIFICATION_EMAIL': env('BREACH_NOTIFICATION_EMAIL', default=''),
    'GDPR_NOTIFICATION_HOURS': 72,
    'CCPA_NOTIFICATION_HOURS': 72,
}

# =============================================================================
# SECURITY TESTING AND VALIDATION
# =============================================================================

# Security Testing
SECURITY_TESTING_ENABLED = True
VULNERABILITY_SCANNING_ENABLED = True
PENETRATION_TESTING_ENABLED = True

# Dependency Scanning
DEPENDENCY_SCANNING = {
    'ENABLED': True,
    'SCAN_FREQUENCY': 'daily',
    'AUTO_UPDATE_MINOR': True,
    'AUTO_UPDATE_SECURITY': True,
}

# Static Code Analysis
STATIC_ANALYSIS = {
    'ENABLED': True,
    'TOOLS': ['bandit', 'semgrep', 'sonarqube'],
    'FAIL_ON_HIGH': True,
    'FAIL_ON_CRITICAL': True,
}

# =============================================================================
# BACKUP AND DISASTER RECOVERY
# =============================================================================

# Backup Security
BACKUP_ENCRYPTION = True
BACKUP_RETENTION_DAYS = 90
BACKUP_GEOGRAPHIC_REPLICATION = True

# Disaster Recovery
DISASTER_RECOVERY_ENABLED = True
RTO_HOURS = 4  # Recovery Time Objective
RPO_HOURS = 1  # Recovery Point Objective

# =============================================================================
# SECURITY MONITORING AND METRICS
# =============================================================================

# Security Metrics
SECURITY_METRICS_ENABLED = True
SECURITY_KPI_TRACKING = True

# Performance Monitoring
SECURITY_PERFORMANCE_MONITORING = True
SLOW_REQUEST_THRESHOLD = 2.0  # 2 seconds

# Health Checks
SECURITY_HEALTH_CHECKS = [
    'database_connection',
    'cache_connection', 
    'vault_connection',
    'external_services',
    'ssl_certificate',
    'security_tools',
]

# =============================================================================
# DEVELOPMENT AND TESTING OVERRIDES
# =============================================================================

if DEBUG:
    # Disable some security features for development
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    
    # Enable additional debugging
    SECURITY_DEBUG = True
    AUDIT_DEBUG = True
    
    # Relaxed rate limiting for development
    for rule in RATE_LIMIT_RULES.values():
        rule['rate'] = rule['rate'].replace('hour', 'minute')

# Test Environment Specific Settings
if 'test' in sys.argv:
    # Speed up password hashing for tests
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
    
    # Disable rate limiting for tests
    RATE_LIMIT_ENABLED = False
    
    # Use in-memory cache for tests
    CACHES['default']['BACKEND'] = 'django.core.cache.backends.locmem.LocMemCache'

# =============================================================================
# FINAL SECURITY VALIDATION
# =============================================================================

# Ensure critical security settings are configured
if not DEBUG:
    required_settings = [
        'SECRET_KEY',
        'ENCRYPTION_MASTER_KEY', 
        'GDPR_DPO_CONTACT',
        'INCIDENT_EMAIL',
        'SECURITY_TEAM_EMAIL',
    ]
    
    missing_settings = []
    for setting in required_settings:
        if not globals().get(setting):
            missing_settings.append(setting)
    
    if missing_settings:
        raise ImproperlyConfigured(
            f"Missing required security settings: {', '.join(missing_settings)}"
        )

# Log security configuration status
import logging
security_logger = logging.getLogger('django.security')
security_logger.info(
    f"Security configuration loaded - "
    f"MFA: {'enabled' if MFA_ENABLED else 'disabled'}, "
    f"Vault: {'enabled' if VAULT_SETTINGS.get('TOKEN') or VAULT_SETTINGS.get('ROLE_ID') else 'disabled'}, "
    f"Rate Limiting: {'enabled' if RATE_LIMIT_ENABLED else 'disabled'}, "
    f"Compliance: GDPR={'enabled' if GDPR_COMPLIANCE['ENABLED'] else 'disabled'} "
    f"CCPA={'enabled' if CCPA_COMPLIANCE['ENABLED'] else 'disabled'} "
    f"SOC2={'enabled' if SOC2_COMPLIANCE['ENABLED'] else 'disabled'}"
)