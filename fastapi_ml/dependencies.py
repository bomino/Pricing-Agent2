"""
FastAPI dependencies for authentication, authorization, and services
"""
import asyncio
import time
from typing import Optional, Dict, Any
from functools import wraps
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis.asyncio as redis
import httpx
from jose import JWTError, jwt
import structlog

from config import settings

logger = structlog.get_logger()
security = HTTPBearer()


# Redis connection
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get Redis client"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=settings.REDIS_TIMEOUT,
            socket_connect_timeout=5,
        )
    return _redis_client


# Rate limiting
class RateLimiter:
    """Rate limiter using Redis"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        burst: int = None
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed under rate limit
        
        Args:
            key: Rate limit key (user_id, IP, etc.)
            limit: Number of requests allowed per window
            window: Time window in seconds
            burst: Burst allowance (optional)
        
        Returns:
            (is_allowed, metadata)
        """
        now = int(time.time())
        pipeline = self.redis.pipeline()
        
        # Remove expired entries
        pipeline.zremrangebyscore(key, 0, now - window)
        
        # Count current requests
        pipeline.zcard(key)
        
        # Add current request
        pipeline.zadd(key, {str(now): now})
        
        # Set expiry
        pipeline.expire(key, window)
        
        results = await pipeline.execute()
        current_requests = results[1]
        
        # Check if allowed
        allowed = current_requests < limit
        
        if burst and not allowed:
            # Check burst allowance
            burst_key = f"{key}:burst"
            burst_count = await self.redis.get(burst_key)
            if burst_count is None:
                burst_count = 0
            else:
                burst_count = int(burst_count)
            
            if burst_count < burst:
                allowed = True
                await self.redis.incr(burst_key)
                await self.redis.expire(burst_key, 60)  # Reset burst every minute
        
        metadata = {
            "limit": limit,
            "window": window,
            "current": current_requests,
            "remaining": max(0, limit - current_requests),
            "reset_at": now + window,
        }
        
        return allowed, metadata


def rate_limit(limit_type: str = "default"):
    """Rate limiting dependency"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get('request') or next((arg for arg in args if isinstance(arg, Request)), None)
            redis_client = await get_redis()
            rate_limiter = RateLimiter(redis_client)
            
            # Get rate limit configuration
            limits = {
                "default": (100, 3600),  # 100 requests per hour
                "ml_predict": (60, 60),   # 60 predictions per minute
                "bulk_operations": (10, 3600),  # 10 bulk operations per hour
            }
            
            limit, window = limits.get(limit_type, limits["default"])
            
            # Create rate limit key
            client_ip = request.client.host if request else "unknown"
            user_id = getattr(request, 'user_id', None) if request else None
            key = f"rate_limit:{limit_type}:{user_id or client_ip}"
            
            # Check rate limit
            allowed, metadata = await rate_limiter.is_allowed(key, limit, window)
            
            if not allowed:
                logger.warning(
                    "Rate limit exceeded",
                    limit_type=limit_type,
                    key=key,
                    metadata=metadata
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {metadata['current']}/{metadata['limit']} requests",
                    headers={
                        "X-RateLimit-Limit": str(metadata['limit']),
                        "X-RateLimit-Remaining": str(metadata['remaining']),
                        "X-RateLimit-Reset": str(metadata['reset_at']),
                        "Retry-After": str(window),
                    }
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Authentication dependencies
async def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(
            token,
            settings.ML_SERVICE_JWT_SECRET,
            algorithms=['HS256']
        )
        
        # Check expiration
        exp = payload.get('exp')
        if exp and time.time() > exp:
            return None
        
        return payload
    
    except JWTError as e:
        logger.debug(f"JWT verification failed: {e}")
        return None


async def verify_service_key(request: Request) -> bool:
    """Verify service-to-service authentication"""
    service_key = request.headers.get("X-ML-Service-Key")
    return service_key == settings.ML_SERVICE_JWT_SECRET


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get current authenticated user"""
    
    # Try JWT token first
    if credentials:
        payload = await verify_jwt_token(credentials.credentials)
        if payload:
            # Create mock user object from JWT payload
            class User:
                def __init__(self, payload):
                    self.id = payload.get('sub')
                    self.email = payload.get('email')
                    self.username = payload.get('username')
                    self.is_staff = payload.get('is_staff', False)
                    self.is_superuser = payload.get('is_superuser', False)
            
            user = User(payload)
            request.user_id = user.id
            return user
    
    # Try service key authentication
    if await verify_service_key(request):
        # Create system user for service requests
        class SystemUser:
            def __init__(self):
                self.id = 'ml_service_system'
                self.email = 'ml-service@pricing-agent.local'
                self.username = 'ml_service_system'
                self.is_staff = True
                self.is_superuser = False
        
        user = SystemUser()
        request.user_id = user.id
        return user
    
    # No valid authentication found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Get current user if authenticated, otherwise None"""
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


async def verify_websocket_token(token: str):
    """Verify WebSocket authentication token"""
    payload = await verify_jwt_token(token)
    if not payload:
        return None
    
    class User:
        def __init__(self, payload):
            self.id = payload.get('sub')
            self.email = payload.get('email')
            self.username = payload.get('username')
            self.is_staff = payload.get('is_staff', False)
    
    return User(payload)


# Service dependencies
_ml_service_instance = None
_model_registry_instance = None

async def get_ml_service():
    """Get ML service instance (singleton)"""
    global _ml_service_instance, _model_registry_instance
    
    if _ml_service_instance is None:
        from .services.ml_service import MLService
        from .services.model_registry import ModelRegistry
        
        # Create model registry
        _model_registry_instance = ModelRegistry()
        
        # Initialize Redis for model registry
        redis_client = await get_redis()
        await _model_registry_instance.initialize_redis(redis_client)
        
        # Create ML service
        _ml_service_instance = MLService(_model_registry_instance)
        
        # Initialize ML service
        await _ml_service_instance.initialize(redis_client)
        
        # Load models
        try:
            await _model_registry_instance.load_models()
        except Exception as e:
            logger.error(f"Failed to load models during ML service initialization: {e}")
    
    return _ml_service_instance


async def get_model_registry():
    """Get model registry instance"""
    global _model_registry_instance
    
    if _model_registry_instance is None:
        # Initialize through get_ml_service to ensure proper setup
        await get_ml_service()
    
    return _model_registry_instance


# Database dependencies (if needed for direct DB access)
async def get_db():
    """Get database connection"""
    # This would typically use SQLAlchemy async session
    # For now, return None as we primarily use Redis and HTTP calls to Django
    return None


# External service dependencies
class DjangoServiceClient:
    """Client for communicating with Django service"""
    
    def __init__(self):
        self.base_url = settings.DJANGO_SERVICE_URL
        self.timeout = settings.DJANGO_SERVICE_TIMEOUT
        self.service_key = settings.ML_SERVICE_JWT_SECRET
    
    async def get(self, endpoint: str, params: Dict = None, user_id: str = None):
        """Make GET request to Django service"""
        return await self._make_request("GET", endpoint, params=params, user_id=user_id)
    
    async def post(self, endpoint: str, data: Dict = None, user_id: str = None):
        """Make POST request to Django service"""
        return await self._make_request("POST", endpoint, json=data, user_id=user_id)
    
    async def _make_request(self, method: str, endpoint: str, **kwargs):
        """Make authenticated request to Django service"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        headers = {
            'X-ML-Service-Key': self.service_key,
            'Content-Type': 'application/json',
        }
        
        # Add user context if provided
        user_id = kwargs.pop('user_id', None)
        if user_id:
            headers['X-User-ID'] = user_id
        
        kwargs['headers'] = headers
        kwargs['timeout'] = self.timeout
        
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()


async def get_django_client() -> DjangoServiceClient:
    """Get Django service client"""
    return DjangoServiceClient()


# Permission dependencies
def require_staff(user = Depends(get_current_user)):
    """Require staff user"""
    if not user.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff privileges required"
        )
    return user


def require_superuser(user = Depends(get_current_user)):
    """Require superuser"""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required"
        )
    return user


# Health check dependencies
async def check_redis_health() -> bool:
    """Check Redis health"""
    try:
        redis_client = await get_redis()
        await redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False


async def check_django_health() -> bool:
    """Check Django service health"""
    try:
        django_client = await get_django_client()
        # Make a simple health check request
        await django_client.get("health/")
        return True
    except Exception as e:
        logger.error(f"Django health check failed: {e}")
        return False


# Caching utilities
async def get_cached_or_compute(
    cache_key: str,
    compute_func,
    ttl: int = 300,  # 5 minutes default
    *args,
    **kwargs
):
    """Get from cache or compute and cache result"""
    redis_client = await get_redis()
    
    # Try to get from cache
    cached_result = await redis_client.get(cache_key)
    if cached_result:
        try:
            import json
            return json.loads(cached_result)
        except:
            pass
    
    # Compute result
    if asyncio.iscoroutinefunction(compute_func):
        result = await compute_func(*args, **kwargs)
    else:
        result = compute_func(*args, **kwargs)
    
    # Cache result
    try:
        import json
        await redis_client.setex(cache_key, ttl, json.dumps(result, default=str))
    except Exception as e:
        logger.warning(f"Failed to cache result: {e}")
    
    return result