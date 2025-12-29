"""
Enterprise Authentication Framework for AI Pricing Agent
Enhanced authentication with MFA, session management, and security controls
"""
import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions
from rest_framework.authentication import BaseAuthentication
from jose import JWTError, jwt as jose_jwt
import httpx
from typing import Optional, Tuple, Any
import logging
from django.core.cache import cache
from django.utils import timezone

from .security import crypto_service, session_manager, mfa_service
from .security_models import SecurityEvent, UserSecuritySettings

User = get_user_model()
logger = logging.getLogger(__name__)


class EnterpriseJWTAuthentication(BaseAuthentication):
    """
    Enterprise JWT authentication with enhanced security features:
    - RSA signature verification
    - Session validation
    - MFA verification tracking
    - Security event logging
    """
    
    def authenticate(self, request) -> Optional[Tuple[User, Any]]:
        """
        Authenticate the request with enhanced security validation
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        try:
            token = auth_header.split(' ')[1]
            payload = self.verify_token(token)
            
            # Get user
            user = self.get_user_from_payload(payload)
            
            # Validate session if present
            session_id = payload.get('session_id')
            session_data = None
            if session_id:
                session_data = session_manager.validate_session(session_id, request)
                if not session_data:
                    SecurityEvent.log_event(
                        'session_expired',
                        user=user,
                        description='Session validation failed',
                        severity='medium',
                        ip_address=self._get_client_ip(request),
                        metadata={'session_id': session_id}
                    )
                    raise exceptions.AuthenticationFailed('Session invalid or expired')
            
            # Check if MFA is required for this request
            if self._requires_mfa_verification(request, user, payload):
                if not payload.get('mfa_verified', False):
                    raise exceptions.AuthenticationFailed('MFA verification required')
            
            return (user, {'payload': payload, 'session_data': session_data})
            
        except (JWTError, User.DoesNotExist, KeyError, IndexError) as e:
            logger.warning(f"JWT authentication failed: {e}")
            SecurityEvent.log_event(
                'login_failure',
                description=f'JWT authentication failed: {str(e)}',
                severity='medium',
                ip_address=self._get_client_ip(request),
                metadata={'error': str(e)}
            )
            raise exceptions.AuthenticationFailed('Invalid token')
    
    def verify_token(self, token: str) -> dict:
        """
        Verify JWT token using enterprise crypto service
        """
        try:
            return crypto_service.verify_jwt_token(token)
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            raise exceptions.AuthenticationFailed(f'Token verification failed: {str(e)}')
    
    def get_user_from_payload(self, payload: dict) -> User:
        """
        Get user from JWT payload with security checks
        """
        user_id = payload.get('sub')
        if not user_id:
            raise exceptions.AuthenticationFailed('Invalid token: missing user ID')
        
        try:
            user = User.objects.get(pk=user_id, is_active=True)
            
            # Check if account is locked
            try:
                security_settings = user.security_settings
                if security_settings.is_account_locked:
                    raise exceptions.AuthenticationFailed('Account is locked')
            except UserSecuritySettings.DoesNotExist:
                # Create default security settings
                UserSecuritySettings.objects.create(user=user)
            
            return user
            
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found or inactive')
    
    @classmethod
    def generate_token(cls, user: User, mfa_verified: bool = False, session_id: str = None, expires_in_minutes: int = None) -> str:
        """
        Generate enterprise JWT token for user
        """
        payload = {
            'sub': str(user.id),
            'email': user.email,
            'username': user.username,
            'mfa_verified': mfa_verified,
            'session_id': session_id,
            'roles': [membership.role for membership in user.organization_memberships.filter(is_active=True)],
        }
        
        return crypto_service.create_jwt_token(payload, expires_in_minutes)
    
    def _requires_mfa_verification(self, request, user, payload) -> bool:
        """
        Check if MFA verification is required for this request
        """
        # Check sensitive endpoints
        sensitive_paths = [
            '/api/v1/admin/',
            '/api/v1/users/',
            '/api/v1/settings/',
            '/api/v1/exports/',
        ]
        
        if any(request.path.startswith(path) for path in sensitive_paths):
            return True
        
        # Check if user has MFA-required role
        if mfa_service.is_mfa_required(user):
            return True
        
        return False
    
    def _get_client_ip(self, request) -> str:
        """
        Get client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class APIKeyAuthentication(BaseAuthentication):
    """
    API Key authentication for service-to-service communication
    """
    
    def authenticate(self, request) -> Optional[Tuple[User, Any]]:
        """
        Authenticate using API key
        """
        api_key_header = request.META.get('HTTP_X_API_KEY')
        if not api_key_header:
            return None
        
        try:
            from accounts.models import APIKey
            api_key_obj = APIKey.verify_key(api_key_header)
            
            if not api_key_obj:
                SecurityEvent.log_event(
                    'login_failure',
                    description='Invalid API key used',
                    severity='high',
                    ip_address=self._get_client_ip(request),
                    metadata={'api_key_prefix': api_key_header[:8] + '...'}
                )
                raise exceptions.AuthenticationFailed('Invalid API key')
            
            # Check if API key is expired
            if api_key_obj.is_expired():
                SecurityEvent.log_event(
                    'login_failure',
                    user=api_key_obj.user,
                    description='Expired API key used',
                    severity='medium',
                    ip_address=self._get_client_ip(request),
                    metadata={'api_key_name': api_key_obj.name}
                )
                raise exceptions.AuthenticationFailed('API key expired')
            
            return (api_key_obj.user, api_key_obj)
            
        except Exception as e:
            logger.error(f"API key authentication failed: {e}")
            raise exceptions.AuthenticationFailed('API key authentication failed')
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class EnhancedMLServiceAuthentication(BaseAuthentication):
    """
    Enhanced ML service authentication with security logging
    """
    
    def authenticate(self, request) -> Optional[Tuple[User, Any]]:
        """
        Authenticate ML service requests with enhanced security
        """
        # Check for ML service header
        ml_service_key = request.META.get('HTTP_X_ML_SERVICE_KEY')
        if not ml_service_key:
            return None
        
        # Verify ML service key using crypto service
        stored_key_hash = getattr(settings, 'ML_SERVICE_KEY_HASH', None)
        if not stored_key_hash or not crypto_service.verify_api_key(ml_service_key, stored_key_hash):
            SecurityEvent.log_event(
                'login_failure',
                description='Invalid ML service key',
                severity='high',
                ip_address=self._get_client_ip(request),
                metadata={'source': 'ml_service'}
            )
            return None
        
        # Check for user context in headers
        user_id = request.META.get('HTTP_X_USER_ID')
        if user_id:
            try:
                user = User.objects.get(pk=user_id, is_active=True)
                return (user, {'service': 'ml_service', 'user_context': True})
            except User.DoesNotExist:
                pass
        
        # Return system user for ML service operations
        system_user = self.get_or_create_system_user()
        return (system_user, {'service': 'ml_service', 'user_context': False})
    
    def get_or_create_system_user(self) -> User:
        """
        Get or create system user for ML service operations
        """
        system_user, created = User.objects.get_or_create(
            username='ml_service_system',
            defaults={
                'email': 'ml-service@pricing-agent.local',
                'is_active': True,
                'is_staff': False,
                'first_name': 'ML',
                'last_name': 'Service',
            }
        )
        return system_user
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class OAuth2Authentication(BaseAuthentication):
    """
    OAuth2/OIDC authentication for enterprise SSO integration
    """
    
    def authenticate(self, request) -> Optional[Tuple[User, Any]]:
        """
        Authenticate using OAuth2 access token
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        # Check if it's an OAuth2 token (different from JWT)
        if not self._is_oauth2_token(token):
            return None
        
        try:
            # Validate token with OAuth2 provider
            user_info = self._validate_oauth2_token(token)
            
            # Get or create user
            user = self._get_or_create_oauth2_user(user_info)
            
            return (user, {'oauth2_token': token, 'user_info': user_info})
            
        except Exception as e:
            logger.warning(f"OAuth2 authentication failed: {e}")
            raise exceptions.AuthenticationFailed('Invalid OAuth2 token')
    
    def _is_oauth2_token(self, token: str) -> bool:
        """
        Check if token is OAuth2 format (not JWT)
        """
        # Simple check: JWT tokens have 3 parts separated by dots
        return len(token.split('.')) != 3
    
    def _validate_oauth2_token(self, token: str) -> dict:
        """
        Validate OAuth2 token with provider
        """
        # This would integrate with your OAuth2 provider (Azure AD, Google, etc.)
        # For now, this is a placeholder implementation
        import requests
        
        oauth2_settings = getattr(settings, 'OAUTH2_SETTINGS', {})
        introspect_url = oauth2_settings.get('INTROSPECT_URL')
        client_id = oauth2_settings.get('CLIENT_ID')
        client_secret = oauth2_settings.get('CLIENT_SECRET')
        
        if not all([introspect_url, client_id, client_secret]):
            raise Exception("OAuth2 not configured")
        
        response = requests.post(introspect_url, data={
            'token': token,
            'client_id': client_id,
            'client_secret': client_secret,
        })
        
        if response.status_code != 200:
            raise Exception("Token validation failed")
        
        token_info = response.json()
        if not token_info.get('active'):
            raise Exception("Token is not active")
        
        return token_info
    
    def _get_or_create_oauth2_user(self, user_info: dict) -> User:
        """
        Get or create user from OAuth2 user info
        """
        email = user_info.get('email')
        if not email:
            raise Exception("No email in token")
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
                is_active=True,
            )
        
        return user


class EnterpriseMLServiceClient:
    """
    Enhanced ML service client with security features
    """
    
    def __init__(self):
        self.base_url = settings.ML_SERVICE_BASE_URL
        self.timeout = settings.ML_SERVICE_TIMEOUT
        self.service_key = settings.ML_SERVICE_JWT_SECRET
    
    async def _make_request(self, method: str, endpoint: str, data=None, user=None, timeout=None):
        """
        Make authenticated request to ML service with enhanced security
        """
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            'X-ML-Service-Key': self.service_key,
            'Content-Type': 'application/json',
        }
        
        # Add user context if provided
        if user:
            headers['X-User-ID'] = str(user.id)
            headers['Authorization'] = f'Bearer {EnterpriseJWTAuthentication.generate_token(user)}'
        
        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data if data else None
                )
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"ML service request failed: {e}")
            SecurityEvent.log_event(
                'ml_service_request_failure',
                user=user,
                description=f'ML service request failed: {str(e)}',
                severity='medium',
                metadata={'endpoint': endpoint, 'error': str(e)}
            )
            raise
    
    async def predict_price(self, material_id: str, quantity: float, user=None, **kwargs):
        """Request price prediction from ML service"""
        data = {
            'material_id': material_id,
            'quantity': quantity,
            **kwargs
        }
        return await self._make_request('POST', '/api/v1/predictions/price', data, user)
    
    async def batch_predict(self, predictions: list, user=None):
        """Request batch predictions from ML service"""
        data = {'predictions': predictions}
        return await self._make_request('POST', '/api/v1/predictions/batch', data, user)
    
    async def detect_anomalies(self, prices: list, user=None):
        """Request anomaly detection from ML service"""
        data = {'prices': prices}
        return await self._make_request('POST', '/api/v1/analytics/anomalies', data, user)
    
    async def forecast_demand(self, material_id: str, periods: int = 30, user=None):
        """Request demand forecast from ML service"""
        data = {
            'material_id': material_id,
            'periods': periods
        }
        return await self._make_request('POST', '/api/v1/analytics/forecast', data, user)
    
    async def health_check(self):
        """Check ML service health"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except:
            return False


class MFARequiredMixin:
    """
    Mixin to require MFA for specific views
    """
    
    def dispatch(self, request, *args, **kwargs):
        """
        Check MFA requirement before processing request
        """
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        
        # Check if MFA is required
        if mfa_service.is_mfa_required(request.user):
            # Check if MFA is verified in current session
            auth_data = getattr(request, 'auth', {})
            if isinstance(auth_data, dict):
                payload = auth_data.get('payload', {})
                if not payload.get('mfa_verified', False):
                    from django.http import JsonResponse
                    return JsonResponse({
                        'error': 'MFA verification required',
                        'code': 'MFA_REQUIRED',
                        'mfa_setup_url': '/api/v1/auth/mfa/setup/',
                    }, status=403)
        
        return super().dispatch(request, *args, **kwargs)


class RateLimitMixin:
    """
    Mixin to apply rate limiting to views
    """
    rate_limit_key = None
    rate_limit_rate = '100/hour'  # Default rate
    
    def dispatch(self, request, *args, **kwargs):
        """
        Apply rate limiting before processing request
        """
        from django_ratelimit.decorators import ratelimit
        from django_ratelimit.exceptions import Ratelimited
        
        # Generate rate limit key
        if self.rate_limit_key:
            key = self.rate_limit_key
        else:
            key = lambda request: request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR')
        
        # Apply rate limiting
        try:
            @ratelimit(key=key, rate=self.rate_limit_rate, method='ALL', block=True)
            def limited_dispatch():
                return super(RateLimitMixin, self).dispatch(request, *args, **kwargs)
            
            return limited_dispatch()
            
        except Ratelimited:
            from django.http import JsonResponse
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'code': 'RATE_LIMIT_EXCEEDED',
            }, status=429)