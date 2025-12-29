"""
Custom middleware for the pricing agent
"""
import json
import logging
import time
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from apps.core.models import AuditLog, Organization
from apps.core.exceptions import OrganizationAccessDenied
import traceback

User = get_user_model()
logger = logging.getLogger(__name__)


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware to log user actions for audit trail
    """
    
    TRACKED_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    EXCLUDED_PATHS = ['/health/', '/admin/jsi18n/', '/static/', '/media/']
    
    def process_request(self, request):
        """Store request start time for performance tracking"""
        request._audit_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Log request for audit if conditions are met"""
        if self.should_log_request(request, response):
            try:
                self.create_audit_log(request, response)
            except Exception as e:
                logger.error(f"Failed to create audit log: {e}")
        
        return response
    
    def should_log_request(self, request, response):
        """Determine if request should be logged"""
        # Skip if path is excluded
        for excluded_path in self.EXCLUDED_PATHS:
            if request.path.startswith(excluded_path):
                return False
        
        # Log all tracked methods
        if request.method in self.TRACKED_METHODS:
            return True
        
        # Log failed GET requests
        if request.method == 'GET' and response.status_code >= 400:
            return True
        
        return False
    
    def create_audit_log(self, request, response):
        """Create audit log entry"""
        # Get user and organization
        user = getattr(request, 'user', None) if hasattr(request, 'user') else None
        if not user or not user.is_authenticated:
            user = None
        
        organization = getattr(request, 'organization', None)
        
        # Determine action
        action = self.get_action(request, response)
        
        # Get object info if available
        object_type, object_id, object_repr = self.get_object_info(request)
        
        # Get IP address
        ip_address = self.get_client_ip(request)
        
        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Get changes (for POST/PUT/PATCH requests)
        changes = self.get_changes(request, response)
        
        # Calculate response time
        response_time = None
        if hasattr(request, '_audit_start_time'):
            response_time = time.time() - request._audit_start_time
        
        # Create audit log
        AuditLog.objects.create(
            user=user,
            organization=organization,
            action=action,
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def get_action(self, request, response):
        """Determine action from request"""
        method = request.method
        path = request.path
        status_code = response.status_code
        
        # API endpoints
        if '/api/' in path:
            if method == 'POST':
                return f"API_CREATE_{status_code}"
            elif method == 'PUT':
                return f"API_UPDATE_{status_code}"
            elif method == 'PATCH':
                return f"API_PARTIAL_UPDATE_{status_code}"
            elif method == 'DELETE':
                return f"API_DELETE_{status_code}"
            elif method == 'GET':
                return f"API_READ_{status_code}"
        
        # Web endpoints
        if method == 'POST':
            if 'login' in path:
                return 'LOGIN_ATTEMPT'
            elif 'logout' in path:
                return 'LOGOUT'
            else:
                return f"WEB_POST_{status_code}"
        
        return f"{method}_{status_code}"
    
    def get_object_info(self, request):
        """Extract object information from request"""
        # Try to get from view if available
        view = getattr(request, 'resolver_match', None)
        if view and hasattr(view, 'func'):
            view_class = getattr(view.func, 'view_class', None)
            if view_class:
                model_class = getattr(view_class, 'model', None) or getattr(view_class, 'queryset', None)
                if model_class:
                    model_name = model_class._meta.label_lower if hasattr(model_class, '_meta') else str(model_class)
                    # Try to get object ID from URL
                    kwargs = view.kwargs
                    object_id = kwargs.get('pk') or kwargs.get('id')
                    return model_name, object_id, None
        
        return None, None, None
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_changes(self, request, response):
        """Extract changes from request"""
        changes = {}
        
        # Include request method and path
        changes['method'] = request.method
        changes['path'] = request.path
        changes['status_code'] = response.status_code
        
        # Include response time if available
        if hasattr(request, '_audit_start_time'):
            changes['response_time_ms'] = round((time.time() - request._audit_start_time) * 1000, 2)
        
        # Include request data for POST/PUT/PATCH
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if hasattr(request, 'data'):
                    # DRF request
                    changes['request_data'] = dict(request.data)
                elif request.content_type == 'application/json':
                    # JSON request
                    changes['request_data'] = json.loads(request.body)
                else:
                    # Form data
                    changes['request_data'] = dict(request.POST)
                
                # Remove sensitive fields
                sensitive_fields = ['password', 'token', 'secret', 'key']
                for field in sensitive_fields:
                    if field in changes.get('request_data', {}):
                        changes['request_data'][field] = '[REDACTED]'
            except:
                pass
        
        return changes


class OrganizationMiddleware(MiddlewareMixin):
    """
    Middleware to handle organization context for multi-tenancy
    """
    
    def process_request(self, request):
        """Set organization context on request"""
        # Skip for non-authenticated requests
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            request.organization = None
            return None
        
        # Get organization from various sources
        organization = self.get_organization_from_request(request)
        
        # Validate user has access to organization
        if organization and not self.user_has_access(request.user, organization):
            raise OrganizationAccessDenied(f"User does not have access to organization: {organization}")
        
        # Set organization on request
        request.organization = organization
        return None
    
    def get_organization_from_request(self, request):
        """Get organization from request"""
        # Try from header first (API requests)
        org_id = request.META.get('HTTP_X_ORGANIZATION_ID')
        if org_id:
            try:
                return Organization.objects.get(id=org_id, is_active=True)
            except Organization.DoesNotExist:
                pass
        
        # Try from user's default organization
        user_profile = getattr(request.user, 'profile', None)
        if user_profile and hasattr(user_profile, 'default_organization'):
            return user_profile.default_organization
        
        # Try from user's organization memberships
        if hasattr(request.user, 'organization_memberships'):
            membership = request.user.organization_memberships.filter(
                organization__is_active=True
            ).first()
            if membership:
                return membership.organization
        
        return None
    
    def user_has_access(self, user, organization):
        """Check if user has access to organization"""
        # Superusers have access to all organizations
        if user.is_superuser:
            return True
        
        # Check organization memberships
        if hasattr(user, 'organization_memberships'):
            return user.organization_memberships.filter(
                organization=organization,
                organization__is_active=True
            ).exists()
        
        return False


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Global error handling middleware
    """
    
    def process_exception(self, request, exception):
        """Handle uncaught exceptions"""
        logger.error(
            f"Unhandled exception in {request.method} {request.path}: {exception}",
            exc_info=True,
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'user': str(request.user) if hasattr(request, 'user') else 'Anonymous',
                'traceback': traceback.format_exc(),
            }
        )
        
        # Return JSON response for API endpoints
        if request.path.startswith('/api/'):
            return JsonResponse({
                'error': 'An unexpected error occurred',
                'detail': str(exception) if settings.DEBUG else 'Internal server error',
                'status_code': 500,
                'timestamp': timezone.now().isoformat(),
            }, status=500)
        
        # Let Django handle other errors with default error pages
        return None


class PerformanceMiddleware(MiddlewareMixin):
    """
    Performance monitoring middleware
    """
    
    def process_request(self, request):
        """Mark request start time"""
        request._performance_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Log slow requests"""
        if hasattr(request, '_performance_start_time'):
            duration = time.time() - request._performance_start_time
            
            # Log slow requests (>2 seconds)
            if duration > 2.0:
                logger.warning(
                    f"Slow request: {request.method} {request.path} took {duration:.2f}s",
                    extra={
                        'request_method': request.method,
                        'request_path': request.path,
                        'duration': duration,
                        'status_code': response.status_code,
                        'user': str(request.user) if hasattr(request, 'user') else 'Anonymous',
                    }
                )
            
            # Add performance header for debugging
            if settings.DEBUG:
                response['X-Response-Time'] = f"{duration:.3f}s"
        
        return response


class CORSMiddleware(MiddlewareMixin):
    """
    Custom CORS middleware for fine-grained control
    """
    
    def process_response(self, request, response):
        """Add CORS headers"""
        # Only add CORS headers for API endpoints
        if request.path.startswith('/api/') or request.path.startswith('/ws/'):
            origin = request.META.get('HTTP_ORIGIN')
            
            # Check if origin is allowed
            allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
            if origin in allowed_origins or settings.DEBUG:
                response['Access-Control-Allow-Origin'] = origin
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-Organization-ID, X-ML-Service-Key'
                response['Access-Control-Max-Age'] = '3600'
        
        return response