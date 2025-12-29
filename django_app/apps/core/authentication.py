"""
Custom authentication classes for the pricing agent
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

User = get_user_model()


class JWTAuthentication(BaseAuthentication):
    """
    Custom JWT authentication for inter-service communication
    """
    
    def authenticate(self, request) -> Optional[Tuple[User, Any]]:
        """
        Authenticate the request and return user and token
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        try:
            token = auth_header.split(' ')[1]
            payload = self.verify_token(token)
            user = self.get_user_from_payload(payload)
            return (user, token)
        except (JWTError, User.DoesNotExist, KeyError, IndexError):
            raise exceptions.AuthenticationFailed('Invalid token')
    
    def verify_token(self, token: str) -> dict:
        """
        Verify and decode JWT token
        """
        try:
            # Use the same secret as FastAPI ML service
            payload = jose_jwt.decode(
                token,
                settings.ML_SERVICE_JWT_SECRET,
                algorithms=['HS256']
            )
            
            # Check expiration
            exp = payload.get('exp')
            if exp and datetime.utcnow().timestamp() > exp:
                raise exceptions.AuthenticationFailed('Token expired')
                
            return payload
        except JWTError as e:
            raise exceptions.AuthenticationFailed(f'Token verification failed: {str(e)}')
    
    def get_user_from_payload(self, payload: dict) -> User:
        """
        Get user from JWT payload
        """
        user_id = payload.get('sub')
        if not user_id:
            raise exceptions.AuthenticationFailed('Invalid token: missing user ID')
        
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found')
    
    @classmethod
    def generate_token(cls, user: User, expires_in_minutes: int = 60) -> str:
        """
        Generate JWT token for user
        """
        expiry = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
        payload = {
            'sub': str(user.id),
            'email': user.email,
            'username': user.username,
            'exp': int(expiry.timestamp()),
            'iat': int(datetime.utcnow().timestamp()),
            'iss': 'pricing-agent-django',
            'aud': 'pricing-agent-ml'
        }
        
        return jose_jwt.encode(
            payload,
            settings.ML_SERVICE_JWT_SECRET,
            algorithm='HS256'
        )


class MLServiceAuthentication(BaseAuthentication):
    """
    Authentication for ML service requests to Django
    """
    
    def authenticate(self, request) -> Optional[Tuple[User, Any]]:
        """
        Authenticate ML service requests
        """
        # Check for ML service header
        ml_service_key = request.META.get('HTTP_X_ML_SERVICE_KEY')
        if ml_service_key != settings.ML_SERVICE_JWT_SECRET:
            return None
        
        # Check for user context in headers
        user_id = request.META.get('HTTP_X_USER_ID')
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
                return (user, 'ml_service')
            except User.DoesNotExist:
                pass
        
        # Return system user for ML service operations
        system_user = self.get_or_create_system_user()
        return (system_user, 'ml_service')
    
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


class OrganizationAuthentication(BaseAuthentication):
    """
    Organization-aware authentication
    """
    
    def authenticate(self, request) -> Optional[Tuple[User, Any]]:
        """
        Authenticate and set organization context
        """
        # Let other authentication backends handle the user
        return None
    
    def authenticate_header(self, request) -> str:
        return 'Bearer'


class MLServiceClient:
    """
    Client for communicating with FastAPI ML service
    """
    
    def __init__(self):
        self.base_url = settings.ML_SERVICE_BASE_URL
        self.timeout = settings.ML_SERVICE_TIMEOUT
        self.service_key = settings.ML_SERVICE_JWT_SECRET
    
    async def _make_request(self, method: str, endpoint: str, data=None, user=None, timeout=None):
        """
        Make authenticated request to ML service
        """
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            'X-ML-Service-Key': self.service_key,
            'Content-Type': 'application/json',
        }
        
        # Add user context if provided
        if user:
            headers['X-User-ID'] = str(user.id)
            headers['Authorization'] = f'Bearer {JWTAuthentication.generate_token(user)}'
        
        async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None
            )
            response.raise_for_status()
            return response.json()
    
    async def predict_price(self, material_id: str, quantity: float, user=None, **kwargs):
        """
        Request price prediction from ML service
        """
        data = {
            'material_id': material_id,
            'quantity': quantity,
            **kwargs
        }
        return await self._make_request('POST', '/api/v1/predictions/price', data, user)
    
    async def batch_predict(self, predictions: list, user=None):
        """
        Request batch predictions from ML service
        """
        data = {'predictions': predictions}
        return await self._make_request('POST', '/api/v1/predictions/batch', data, user)
    
    async def detect_anomalies(self, prices: list, user=None):
        """
        Request anomaly detection from ML service
        """
        data = {'prices': prices}
        return await self._make_request('POST', '/api/v1/analytics/anomalies', data, user)
    
    async def forecast_demand(self, material_id: str, periods: int = 30, user=None):
        """
        Request demand forecast from ML service
        """
        data = {
            'material_id': material_id,
            'periods': periods
        }
        return await self._make_request('POST', '/api/v1/analytics/forecast', data, user)
    
    async def health_check(self):
        """
        Check ML service health
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except:
            return False