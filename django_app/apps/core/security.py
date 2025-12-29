"""
Enterprise Security Framework for AI Pricing Agent
Implements comprehensive security controls for authentication, authorization, and data protection
"""
import hashlib
import hmac
import secrets
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.core.cache import cache
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models, transaction
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
import pyotp
import qrcode
import io
import base64

from .exceptions import SecurityException, AuthenticationException, AuthorizationException

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Security configuration constants"""
    # Password policies
    MIN_PASSWORD_LENGTH: int = 12
    MAX_PASSWORD_LENGTH: int = 256
    REQUIRE_UPPERCASE: bool = True
    REQUIRE_LOWERCASE: bool = True
    REQUIRE_DIGITS: bool = True
    REQUIRE_SPECIAL_CHARS: bool = True
    PASSWORD_HISTORY_COUNT: int = 12
    PASSWORD_EXPIRY_DAYS: int = 90
    
    # Account lockout
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30
    PROGRESSIVE_LOCKOUT: bool = True
    
    # Session security
    SESSION_TIMEOUT_MINUTES: int = 120
    CONCURRENT_SESSIONS_LIMIT: int = 3
    SESSION_FINGERPRINTING: bool = True
    
    # MFA settings
    ENFORCE_MFA_ROLES: List[str] = None
    TOTP_WINDOW: int = 1
    BACKUP_CODES_COUNT: int = 10
    
    # JWT settings
    JWT_EXPIRY_MINUTES: int = 60
    JWT_REFRESH_EXPIRY_HOURS: int = 24
    JWT_ALGORITHM: str = 'RS256'
    
    # Rate limiting
    API_RATE_LIMIT_PER_MINUTE: int = 100
    AUTH_RATE_LIMIT_PER_MINUTE: int = 20
    
    def __post_init__(self):
        if self.ENFORCE_MFA_ROLES is None:
            self.ENFORCE_MFA_ROLES = ['admin', 'manager', 'owner']


class CryptoService:
    """Cryptographic operations service"""
    
    def __init__(self):
        self.config = SecurityConfig()
        self._init_keys()
    
    def _init_keys(self):
        """Initialize encryption keys"""
        # Generate or load RSA keys for JWT
        if hasattr(settings, 'RSA_PRIVATE_KEY') and hasattr(settings, 'RSA_PUBLIC_KEY'):
            self.private_key = serialization.load_pem_private_key(
                settings.RSA_PRIVATE_KEY.encode(),
                password=None,
                backend=default_backend()
            )
            self.public_key = serialization.load_pem_public_key(
                settings.RSA_PUBLIC_KEY.encode(),
                backend=default_backend()
            )
        else:
            # Generate new keys (should be stored in production)
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            self.public_key = self.private_key.public_key()
            logger.warning("Generated new RSA keys - store these in production!")
    
    def encrypt_sensitive_data(self, data: str, context: str = "") -> str:
        """Encrypt sensitive data using AES-256-GCM"""
        key = self._derive_key(context)
        
        # Generate random IV
        iv = secrets.token_bytes(12)
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data.encode()) + encryptor.finalize()
        
        # Combine IV + auth tag + ciphertext
        encrypted = iv + encryptor.tag + ciphertext
        return base64.b64encode(encrypted).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str, context: str = "") -> str:
        """Decrypt sensitive data using AES-256-GCM"""
        try:
            data = base64.b64decode(encrypted_data.encode())
            key = self._derive_key(context)
            
            # Extract components
            iv = data[:12]
            tag = data[12:28]
            ciphertext = data[28:]
            
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext.decode()
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise SecurityException("Data decryption failed")
    
    def _derive_key(self, context: str) -> bytes:
        """Derive encryption key from master key and context"""
        master_key = getattr(settings, 'ENCRYPTION_MASTER_KEY', settings.SECRET_KEY).encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=context.encode() + b'pricing_agent_salt',
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(master_key)
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash API key for storage"""
        salt = secrets.token_bytes(32)
        key_hash = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt, 100000)
        return base64.b64encode(salt + key_hash).decode()
    
    def verify_api_key(self, api_key: str, stored_hash: str) -> bool:
        """Verify API key against stored hash"""
        try:
            decoded = base64.b64decode(stored_hash.encode())
            salt = decoded[:32]
            stored_key_hash = decoded[32:]
            key_hash = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt, 100000)
            return hmac.compare_digest(stored_key_hash, key_hash)
        except:
            return False
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    def create_jwt_token(self, payload: Dict, expires_in_minutes: int = None) -> str:
        """Create JWT token with RSA signature"""
        if expires_in_minutes is None:
            expires_in_minutes = self.config.JWT_EXPIRY_MINUTES
            
        now = datetime.utcnow()
        payload.update({
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(minutes=expires_in_minutes)).timestamp()),
            'iss': 'pricing-agent',
            'jti': secrets.token_urlsafe(16),
        })
        
        return jwt.encode(
            payload,
            self.private_key,
            algorithm=self.config.JWT_ALGORITHM
        )
    
    def verify_jwt_token(self, token: str) -> Dict:
        """Verify JWT token with RSA signature"""
        try:
            return jwt.decode(
                token,
                self.public_key,
                algorithms=[self.config.JWT_ALGORITHM],
                issuer='pricing-agent'
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT verification failed: {e}")
            raise AuthenticationException("Invalid token")


class PasswordPolicy:
    """Password policy enforcement"""
    
    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
    
    def validate_password(self, password: str, user=None) -> List[str]:
        """Validate password against policy"""
        errors = []
        
        # Length checks
        if len(password) < self.config.MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {self.config.MIN_PASSWORD_LENGTH} characters long")
        
        if len(password) > self.config.MAX_PASSWORD_LENGTH:
            errors.append(f"Password cannot exceed {self.config.MAX_PASSWORD_LENGTH} characters")
        
        # Character requirements
        if self.config.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.config.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.config.REQUIRE_DIGITS and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if self.config.REQUIRE_SPECIAL_CHARS:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                errors.append("Password must contain at least one special character")
        
        # Common password checks
        if self._is_common_password(password):
            errors.append("Password is too common")
        
        # User-specific checks
        if user:
            if self._contains_personal_info(password, user):
                errors.append("Password cannot contain personal information")
            
            if self._is_in_password_history(password, user):
                errors.append(f"Password was used recently. Cannot reuse last {self.config.PASSWORD_HISTORY_COUNT} passwords")
        
        return errors
    
    def _is_common_password(self, password: str) -> bool:
        """Check if password is in common passwords list"""
        # In production, this would check against a comprehensive list
        common_passwords = [
            'password', '123456', 'admin', 'letmein', 'welcome',
            'password123', 'admin123', 'qwerty', 'abc123'
        ]
        return password.lower() in [p.lower() for p in common_passwords]
    
    def _contains_personal_info(self, password: str, user) -> bool:
        """Check if password contains personal information"""
        password_lower = password.lower()
        
        # Check username, email, names
        checks = [
            user.username.lower() if user.username else '',
            user.email.lower().split('@')[0],
            user.first_name.lower() if user.first_name else '',
            user.last_name.lower() if user.last_name else '',
        ]
        
        return any(check and check in password_lower for check in checks if len(check) >= 3)
    
    def _is_in_password_history(self, password: str, user) -> bool:
        """Check if password was used recently"""
        try:
            from .models import PasswordHistory
            recent_passwords = PasswordHistory.objects.filter(
                user=user
            ).order_by('-created_at')[:self.config.PASSWORD_HISTORY_COUNT]
            
            for pwd_history in recent_passwords:
                if check_password(password, pwd_history.password_hash):
                    return True
            
            return False
        except:
            return False


class MFAService:
    """Multi-Factor Authentication service"""
    
    def __init__(self, crypto_service: CryptoService = None):
        self.crypto = crypto_service or CryptoService()
    
    def setup_totp(self, user) -> Dict[str, str]:
        """Setup TOTP for user"""
        secret = pyotp.random_base32()
        
        # Store encrypted secret
        encrypted_secret = self.crypto.encrypt_sensitive_data(secret, f"totp_{user.id}")
        
        # Update or create MFA settings
        from .models import UserSecuritySettings
        settings_obj, created = UserSecuritySettings.objects.get_or_create(
            user=user,
            defaults={'totp_secret': encrypted_secret}
        )
        if not created:
            settings_obj.totp_secret = encrypted_secret
            settings_obj.save()
        
        # Generate QR code
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name="AI Pricing Agent"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        qr_code = base64.b64encode(img_buffer.getvalue()).decode()
        
        return {
            'secret': secret,
            'qr_code': qr_code,
            'backup_codes': self.generate_backup_codes(user)
        }
    
    def verify_totp(self, user, token: str) -> bool:
        """Verify TOTP token"""
        try:
            from .models import UserSecuritySettings
            security_settings = UserSecuritySettings.objects.get(user=user)
            
            if not security_settings.totp_secret:
                return False
            
            secret = self.crypto.decrypt_sensitive_data(
                security_settings.totp_secret,
                f"totp_{user.id}"
            )
            
            totp = pyotp.TOTP(secret)
            return totp.verify(token, valid_window=SecurityConfig().TOTP_WINDOW)
            
        except Exception as e:
            logger.error(f"TOTP verification failed for user {user.id}: {e}")
            return False
    
    def generate_backup_codes(self, user) -> List[str]:
        """Generate backup codes for user"""
        codes = []
        for _ in range(SecurityConfig().BACKUP_CODES_COUNT):
            code = secrets.token_hex(4).upper()
            codes.append(code)
        
        # Store encrypted backup codes
        from .models import UserSecuritySettings
        security_settings, created = UserSecuritySettings.objects.get_or_create(user=user)
        
        encrypted_codes = []
        for code in codes:
            encrypted_code = self.crypto.encrypt_sensitive_data(code, f"backup_{user.id}")
            encrypted_codes.append(encrypted_code)
        
        security_settings.backup_codes = encrypted_codes
        security_settings.save()
        
        return codes
    
    def verify_backup_code(self, user, code: str) -> bool:
        """Verify and consume backup code"""
        try:
            from .models import UserSecuritySettings
            security_settings = UserSecuritySettings.objects.get(user=user)
            
            if not security_settings.backup_codes:
                return False
            
            # Check each backup code
            for i, encrypted_code in enumerate(security_settings.backup_codes):
                try:
                    stored_code = self.crypto.decrypt_sensitive_data(
                        encrypted_code,
                        f"backup_{user.id}"
                    )
                    
                    if hmac.compare_digest(stored_code.upper(), code.upper()):
                        # Remove used code
                        security_settings.backup_codes.pop(i)
                        security_settings.save()
                        return True
                        
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Backup code verification failed for user {user.id}: {e}")
            return False
    
    def is_mfa_required(self, user) -> bool:
        """Check if MFA is required for user"""
        config = SecurityConfig()
        
        # Check user roles
        try:
            user_roles = [membership.role for membership in user.organization_memberships.all()]
            if any(role in config.ENFORCE_MFA_ROLES for role in user_roles):
                return True
        except:
            pass
        
        # Check if user has enabled MFA
        try:
            from .models import UserSecuritySettings
            settings = UserSecuritySettings.objects.get(user=user)
            return settings.mfa_enabled
        except:
            return False


class SessionManager:
    """Secure session management"""
    
    def __init__(self, crypto_service: CryptoService = None):
        self.crypto = crypto_service or CryptoService()
        self.config = SecurityConfig()
    
    def create_session(self, user, request, mfa_verified: bool = False) -> Dict[str, Any]:
        """Create secure session"""
        session_id = self.crypto.generate_secure_token()
        
        # Generate session fingerprint
        fingerprint = self._generate_fingerprint(request)
        
        # Create session data
        session_data = {
            'user_id': str(user.id),
            'created_at': datetime.utcnow().isoformat(),
            'last_activity': datetime.utcnow().isoformat(),
            'fingerprint': fingerprint,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'mfa_verified': mfa_verified,
            'organization_id': getattr(request, 'organization', {}).get('id') if hasattr(request, 'organization') else None,
        }
        
        # Store session in cache with expiration
        cache.set(
            f"session:{session_id}",
            session_data,
            timeout=self.config.SESSION_TIMEOUT_MINUTES * 60
        )
        
        # Track active sessions for user
        self._track_user_session(user.id, session_id)
        
        # Generate JWT token
        token_payload = {
            'sub': str(user.id),
            'session_id': session_id,
            'mfa_verified': mfa_verified,
            'fingerprint': fingerprint,
        }
        
        access_token = self.crypto.create_jwt_token(
            token_payload,
            self.config.JWT_EXPIRY_MINUTES
        )
        
        refresh_token = self.crypto.create_jwt_token(
            {'sub': str(user.id), 'session_id': session_id, 'type': 'refresh'},
            self.config.JWT_REFRESH_EXPIRY_HOURS * 60
        )
        
        return {
            'session_id': session_id,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': self.config.JWT_EXPIRY_MINUTES * 60,
        }
    
    def validate_session(self, session_id: str, request) -> Optional[Dict[str, Any]]:
        """Validate and refresh session"""
        session_data = cache.get(f"session:{session_id}")
        
        if not session_data:
            return None
        
        # Check session expiry
        last_activity = datetime.fromisoformat(session_data['last_activity'])
        if datetime.utcnow() - last_activity > timedelta(minutes=self.config.SESSION_TIMEOUT_MINUTES):
            self.destroy_session(session_id)
            return None
        
        # Verify fingerprint
        current_fingerprint = self._generate_fingerprint(request)
        if not hmac.compare_digest(session_data['fingerprint'], current_fingerprint):
            logger.warning(f"Session fingerprint mismatch for session {session_id}")
            self.destroy_session(session_id)
            return None
        
        # Update last activity
        session_data['last_activity'] = datetime.utcnow().isoformat()
        cache.set(
            f"session:{session_id}",
            session_data,
            timeout=self.config.SESSION_TIMEOUT_MINUTES * 60
        )
        
        return session_data
    
    def destroy_session(self, session_id: str):
        """Destroy session"""
        session_data = cache.get(f"session:{session_id}")
        if session_data:
            user_id = session_data['user_id']
            self._untrack_user_session(user_id, session_id)
        
        cache.delete(f"session:{session_id}")
    
    def destroy_all_user_sessions(self, user_id: str):
        """Destroy all sessions for user"""
        session_ids = cache.get(f"user_sessions:{user_id}", [])
        for session_id in session_ids:
            cache.delete(f"session:{session_id}")
        cache.delete(f"user_sessions:{user_id}")
    
    def _generate_fingerprint(self, request) -> str:
        """Generate session fingerprint"""
        components = [
            request.META.get('HTTP_USER_AGENT', ''),
            request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            request.META.get('HTTP_ACCEPT_ENCODING', ''),
            self._get_client_ip(request),
        ]
        
        fingerprint_data = '|'.join(components)
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    
    def _track_user_session(self, user_id: str, session_id: str):
        """Track session for user"""
        sessions = cache.get(f"user_sessions:{user_id}", [])
        sessions.append(session_id)
        
        # Enforce concurrent session limit
        if len(sessions) > self.config.CONCURRENT_SESSIONS_LIMIT:
            # Remove oldest session
            oldest_session = sessions.pop(0)
            cache.delete(f"session:{oldest_session}")
        
        cache.set(f"user_sessions:{user_id}", sessions)
    
    def _untrack_user_session(self, user_id: str, session_id: str):
        """Remove session from user tracking"""
        sessions = cache.get(f"user_sessions:{user_id}", [])
        if session_id in sessions:
            sessions.remove(session_id)
            cache.set(f"user_sessions:{user_id}", sessions)


# Global instances
crypto_service = CryptoService()
password_policy = PasswordPolicy()
mfa_service = MFAService(crypto_service)
session_manager = SessionManager(crypto_service)


class SecurityMixin:
    """Security mixin for Django REST Framework viewsets"""
    
    def check_permissions(self, request):
        """Enhanced permission checking"""
        super().check_permissions(request)
        
        # Additional security checks
        if hasattr(self, 'required_roles'):
            if not self._check_user_roles(request.user, self.required_roles):
                raise AuthorizationException("User lacks required role")
        
        # Check organization access
        if hasattr(self, 'organization_field'):
            self._check_organization_access(request)
    
    def _check_user_roles(self, user, required_roles):
        """Check if user has required roles"""
        if not user.is_authenticated:
            return False
        
        if hasattr(user, 'profile') and hasattr(user.profile, 'role'):
            return user.profile.role in required_roles
        
        return False
    
    def _check_organization_access(self, request):
        """Check organization-level access"""
        if not request.user.is_authenticated:
            raise AuthenticationException("Authentication required")
        
        # Get organization from request or object
        org_id = request.data.get('organization') or request.GET.get('organization')
        
        if org_id and hasattr(request.user, 'profile'):
            if str(request.user.profile.organization_id) != str(org_id):
                raise AuthorizationException("Access denied to this organization")


class AuditMixin:
    """Audit logging mixin for Django REST Framework viewsets"""
    
    def perform_create(self, serializer):
        """Audit object creation"""
        instance = serializer.save()
        self._log_audit_event('CREATE', instance)
        return instance
    
    def perform_update(self, serializer):
        """Audit object update"""
        old_instance = self.get_object()
        old_data = self._serialize_instance(old_instance)
        
        instance = serializer.save()
        new_data = self._serialize_instance(instance)
        
        self._log_audit_event('UPDATE', instance, {
            'old': old_data,
            'new': new_data,
            'changes': self._get_changes(old_data, new_data)
        })
        return instance
    
    def perform_destroy(self, instance):
        """Audit object deletion"""
        data = self._serialize_instance(instance)
        self._log_audit_event('DELETE', instance, {'deleted_data': data})
        super().perform_destroy(instance)
    
    def _log_audit_event(self, action, instance, details=None):
        """Log audit event"""
        from apps.core.models import AuditLog
        
        AuditLog.objects.create(
            user=self.request.user,
            action=action,
            model_name=instance.__class__.__name__,
            object_id=str(instance.pk),
            details=details or {},
            ip_address=self._get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            organization_id=getattr(instance, 'organization_id', None)
        )
    
    def _serialize_instance(self, instance):
        """Serialize model instance for audit logging"""
        from django.forms.models import model_to_dict
        try:
            return model_to_dict(instance)
        except:
            return str(instance)
    
    def _get_changes(self, old_data, new_data):
        """Get changes between old and new data"""
        changes = {}
        
        # Handle dict comparison
        if isinstance(old_data, dict) and isinstance(new_data, dict):
            all_keys = set(old_data.keys()) | set(new_data.keys())
            for key in all_keys:
                old_val = old_data.get(key)
                new_val = new_data.get(key)
                if old_val != new_val:
                    changes[key] = {'old': old_val, 'new': new_val}
        
        return changes
    
    def _get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return self.request.META.get('REMOTE_ADDR', '')