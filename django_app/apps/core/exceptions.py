"""
Custom exceptions for the pricing agent
"""
from rest_framework import status
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from django.http import Http404
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
import logging

logger = logging.getLogger(__name__)


class PricingAgentException(Exception):
    """Base exception for pricing agent"""
    default_message = "An error occurred"
    default_code = "error"
    default_status = status.HTTP_400_BAD_REQUEST
    
    def __init__(self, message=None, code=None, status_code=None, details=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.status_code = status_code or self.default_status
        self.details = details or {}
        super().__init__(self.message)


class OrganizationAccessDenied(PricingAgentException):
    """Raised when user doesn't have access to organization"""
    default_message = "Access denied to organization"
    default_code = "organization_access_denied"
    default_status = status.HTTP_403_FORBIDDEN


class MLServiceError(PricingAgentException):
    """Raised when ML service encounters an error"""
    default_message = "ML service error"
    default_code = "ml_service_error"
    default_status = status.HTTP_503_SERVICE_UNAVAILABLE


class MLServiceUnavailable(MLServiceError):
    """Raised when ML service is unavailable"""
    default_message = "ML service is currently unavailable"
    default_code = "ml_service_unavailable"


class InvalidPredictionRequest(PricingAgentException):
    """Raised when prediction request is invalid"""
    default_message = "Invalid prediction request"
    default_code = "invalid_prediction_request"


class MaterialNotFound(PricingAgentException):
    """Raised when material is not found"""
    default_message = "Material not found"
    default_code = "material_not_found"
    default_status = status.HTTP_404_NOT_FOUND


class SupplierNotFound(PricingAgentException):
    """Raised when supplier is not found"""
    default_message = "Supplier not found"
    default_code = "supplier_not_found"
    default_status = status.HTTP_404_NOT_FOUND


class QuoteNotFound(PricingAgentException):
    """Raised when quote is not found"""
    default_message = "Quote not found"
    default_code = "quote_not_found"
    default_status = status.HTTP_404_NOT_FOUND


class DuplicateQuoteError(PricingAgentException):
    """Raised when duplicate quote is submitted"""
    default_message = "Duplicate quote submission"
    default_code = "duplicate_quote"
    default_status = status.HTTP_409_CONFLICT


class WorkflowError(PricingAgentException):
    """Raised when workflow operation fails"""
    default_message = "Workflow operation failed"
    default_code = "workflow_error"


class InvalidWorkflowTransition(WorkflowError):
    """Raised when workflow transition is invalid"""
    default_message = "Invalid workflow transition"
    default_code = "invalid_workflow_transition"


class InsufficientPermissions(PricingAgentException):
    """Raised when user lacks required permissions"""
    default_message = "Insufficient permissions"
    default_code = "insufficient_permissions"
    default_status = status.HTTP_403_FORBIDDEN


class DataValidationError(PricingAgentException):
    """Raised when data validation fails"""
    default_message = "Data validation failed"
    default_code = "validation_error"


class IntegrationError(PricingAgentException):
    """Raised when external integration fails"""
    default_message = "External integration error"
    default_code = "integration_error"
    default_status = status.HTTP_502_BAD_GATEWAY


class ERPIntegrationError(IntegrationError):
    """Raised when ERP integration fails"""
    default_message = "ERP integration error"
    default_code = "erp_integration_error"


class RateLimitExceeded(PricingAgentException):
    """Raised when rate limit is exceeded"""
    default_message = "Rate limit exceeded"
    default_code = "rate_limit_exceeded"
    default_status = status.HTTP_429_TOO_MANY_REQUESTS


class SecurityException(PricingAgentException):
    """Base security exception"""
    default_message = "Security violation"
    default_code = "security_error"
    default_status = status.HTTP_403_FORBIDDEN


class AuthenticationException(SecurityException):
    """Raised when authentication fails"""
    default_message = "Authentication failed"
    default_code = "authentication_failed"
    default_status = status.HTTP_401_UNAUTHORIZED


class AuthorizationException(SecurityException):
    """Raised when authorization fails"""
    default_message = "Authorization failed"
    default_code = "authorization_failed"
    default_status = status.HTTP_403_FORBIDDEN


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF
    """
    # Get the standard error response first
    response = drf_exception_handler(exc, context)
    
    # Handle our custom exceptions
    if isinstance(exc, PricingAgentException):
        response_data = {
            'error': {
                'code': exc.code,
                'message': exc.message,
                'details': exc.details,
            },
            'status_code': exc.status_code,
        }
        
        # Add request context for debugging
        if hasattr(context, 'request'):
            request = context['request']
            response_data['error']['request_id'] = getattr(request, 'id', None)
            response_data['error']['path'] = request.path
            response_data['error']['method'] = request.method
        
        response = Response(response_data, status=exc.status_code)
    
    # Handle standard Django exceptions
    elif isinstance(exc, Http404):
        response_data = {
            'error': {
                'code': 'not_found',
                'message': 'The requested resource was not found',
            },
            'status_code': status.HTTP_404_NOT_FOUND,
        }
        response = Response(response_data, status=status.HTTP_404_NOT_FOUND)
    
    elif isinstance(exc, PermissionDenied):
        response_data = {
            'error': {
                'code': 'permission_denied',
                'message': 'You do not have permission to perform this action',
            },
            'status_code': status.HTTP_403_FORBIDDEN,
        }
        response = Response(response_data, status=status.HTTP_403_FORBIDDEN)
    
    elif isinstance(exc, DjangoValidationError):
        response_data = {
            'error': {
                'code': 'validation_error',
                'message': 'Validation failed',
                'details': exc.message_dict if hasattr(exc, 'message_dict') else str(exc),
            },
            'status_code': status.HTTP_400_BAD_REQUEST,
        }
        response = Response(response_data, status=status.HTTP_400_BAD_REQUEST)
    
    # Log the error
    if response is not None and response.status_code >= 500:
        logger.error(
            f"Server error: {exc}",
            exc_info=True,
            extra={
                'request_path': context.get('request', {}).path if context.get('request') else None,
                'request_method': context.get('request', {}).method if context.get('request') else None,
                'user': str(context.get('request', {}).user) if context.get('request') else None,
                'status_code': response.status_code,
            }
        )
    elif response is not None and response.status_code >= 400:
        logger.warning(
            f"Client error: {exc}",
            extra={
                'request_path': context.get('request', {}).path if context.get('request') else None,
                'request_method': context.get('request', {}).method if context.get('request') else None,
                'user': str(context.get('request', {}).user) if context.get('request') else None,
                'status_code': response.status_code,
            }
        )
    
    return response


class ErrorResponse:
    """Helper class for consistent error responses"""
    
    @staticmethod
    def create(code, message, details=None, status_code=400):
        """Create standardized error response"""
        return {
            'error': {
                'code': code,
                'message': message,
                'details': details or {},
            },
            'status_code': status_code,
        }
    
    @staticmethod
    def validation_error(errors):
        """Create validation error response"""
        return ErrorResponse.create(
            code='validation_error',
            message='Validation failed',
            details=errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    @staticmethod
    def not_found(resource='Resource'):
        """Create not found error response"""
        return ErrorResponse.create(
            code='not_found',
            message=f'{resource} not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    @staticmethod
    def permission_denied(action='perform this action'):
        """Create permission denied error response"""
        return ErrorResponse.create(
            code='permission_denied',
            message=f'You do not have permission to {action}',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    @staticmethod
    def server_error(message='An internal server error occurred'):
        """Create server error response"""
        return ErrorResponse.create(
            code='server_error',
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    @staticmethod
    def service_unavailable(service='Service'):
        """Create service unavailable error response"""
        return ErrorResponse.create(
            code='service_unavailable',
            message=f'{service} is currently unavailable',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )