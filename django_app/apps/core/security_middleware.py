"""
Enterprise Security Middleware for AI Pricing Agent
Comprehensive security controls including headers, rate limiting, and threat detection
"""
import json
import logging
import time
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousOperation

from .security_models import SecurityEvent, UserSecuritySettings
from .security import SecurityConfig

User = get_user_model()
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add comprehensive security headers for defense in depth
    """
    
    def process_response(self, request, response):
        """Add security headers to response"""
        
        # Content Security Policy (CSP)
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: blob: https:",
            "connect-src 'self' wss: ws:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        
        if not settings.DEBUG:
            csp_directives.extend([
                "upgrade-insecure-requests",
                "block-all-mixed-content",
            ])
        
        response['Content-Security-Policy'] = '; '.join(csp_directives)
        
        # Security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            'Cross-Origin-Embedder-Policy': 'require-corp',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'same-origin',
        }
        
        # HSTS for HTTPS
        if request.is_secure() and not settings.DEBUG:
            security_headers.update({
                'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            })
        
        # Add all headers
        for header, value in security_headers.items():
            response[header] = value
        
        # Remove server information
        if 'Server' in response:
            del response['Server']
        
        # Add custom headers
        response['X-Powered-By'] = 'AI Pricing Agent'
        
        return response


class ThreatDetectionMiddleware(MiddlewareMixin):
    """
    Advanced threat detection and blocking middleware
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.config = SecurityConfig()
        
        # Threat patterns
        self.sql_injection_patterns = [
            r"union\s+select", r"select\s+.*\s+from", r"insert\s+into",
            r"update\s+.*\s+set", r"delete\s+from", r"drop\s+table",
            r"--", r"/\*", r"\*/", r"xp_cmdshell", r"sp_executesql"
        ]
        
        self.xss_patterns = [
            r"<script", r"javascript:", r"on\w+\s*=", r"expression\s*\(",
            r"vbscript:", r"data:text/html", r"<iframe", r"<object",
            r"<embed", r"<link.*javascript"
        ]
        
        self.path_traversal_patterns = [
            r"\.\.\/", r"\.\.\\"", r"\.\.%2f", r"\.\.%5c",
            r"%2e%2e%2f", r"%2e%2e%5c"
        ]
        
        # Suspicious patterns
        self.suspicious_patterns = [
            r"curl", r"wget", r"python", r"perl", r"php",
            r"bash", r"cmd", r"powershell", r"eval\("
        ]
    
    def process_request(self, request):
        """Detect and block threats in incoming requests"""
        
        # Get client info
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check IP blacklist
        if self._is_ip_blacklisted(ip_address):
            logger.warning(f"Blocked request from blacklisted IP: {ip_address}")
            return HttpResponse("Access Denied", status=403)
        
        # Rate limiting by IP
        if self._is_rate_limited(ip_address, 'ip_limit'):
            SecurityEvent.log_event(
                'suspicious_activity',
                description=f'Rate limit exceeded for IP {ip_address}',
                severity='medium',
                ip_address=ip_address,
                metadata={'type': 'rate_limit', 'user_agent': user_agent}
            )
            return HttpResponse("Rate limit exceeded", status=429)
        
        # Check for malicious patterns
        threat_detected = self._scan_for_threats(request)
        if threat_detected:
            self._handle_threat(request, threat_detected)
            return HttpResponse("Security violation detected", status=400)
        
        # Check user agent
        if self._is_suspicious_user_agent(user_agent):
            SecurityEvent.log_event(
                'suspicious_activity',
                description=f'Suspicious user agent: {user_agent}',
                severity='low',
                ip_address=ip_address,
                metadata={'type': 'suspicious_user_agent', 'user_agent': user_agent}
            )
        
        return None
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    
    def _is_ip_blacklisted(self, ip_address: str) -> bool:
        """Check if IP is blacklisted"""
        blacklist_key = f"ip_blacklist:{ip_address}"
        return cache.get(blacklist_key, False)
    
    def _is_rate_limited(self, identifier: str, limit_type: str) -> bool:
        """Check rate limiting"""
        cache_key = f"rate_limit:{limit_type}:{identifier}"
        current_count = cache.get(cache_key, 0)
        
        # Different limits for different types
        limits = {
            'ip_limit': 1000,  # requests per hour
            'user_limit': 2000,
            'api_limit': 5000,
        }
        
        limit = limits.get(limit_type, 1000)
        
        if current_count >= limit:
            return True
        
        # Increment counter
        cache.set(cache_key, current_count + 1, timeout=3600)  # 1 hour
        return False
    
    def _scan_for_threats(self, request) -> Optional[str]:
        """Scan request for threat patterns"""
        
        # Collect all input data
        all_data = []
        
        # URL and query parameters
        all_data.append(request.path)
        all_data.append(request.META.get('QUERY_STRING', ''))
        
        # POST data
        if hasattr(request, 'body') and request.body:
            try:
                body_str = request.body.decode('utf-8')
                all_data.append(body_str)
            except:
                pass
        
        # Headers (selected ones)
        suspicious_headers = ['HTTP_REFERER', 'HTTP_USER_AGENT', 'HTTP_X_FORWARDED_FOR']
        for header in suspicious_headers:
            if header in request.META:
                all_data.append(request.META[header])
        
        # Check each data source
        for data in all_data:
            if not data:
                continue
                
            data_lower = data.lower()
            
            # SQL Injection
            for pattern in self.sql_injection_patterns:
                if re.search(pattern, data_lower, re.IGNORECASE):
                    return f"SQL Injection: {pattern}"
            
            # XSS
            for pattern in self.xss_patterns:
                if re.search(pattern, data_lower, re.IGNORECASE):
                    return f"XSS: {pattern}"
            
            # Path Traversal
            for pattern in self.path_traversal_patterns:
                if re.search(pattern, data_lower, re.IGNORECASE):
                    return f"Path Traversal: {pattern}"
            
            # Command Injection
            for pattern in self.suspicious_patterns:
                if re.search(r'\b' + pattern + r'\b', data_lower, re.IGNORECASE):
                    return f"Command Injection: {pattern}"
        
        return None
    
    def _handle_threat(self, request, threat_type: str):
        """Handle detected threat"""
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Log security event
        SecurityEvent.log_event(
            'suspicious_activity',
            user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
            description=f'Security threat detected: {threat_type}',
            severity='high',
            ip_address=ip_address,
            metadata={
                'threat_type': threat_type,
                'path': request.path,
                'method': request.method,
                'user_agent': user_agent,
                'query_string': request.META.get('QUERY_STRING', ''),
            }
        )
        
        # Blacklist IP temporarily
        blacklist_key = f"ip_blacklist:{ip_address}"
        cache.set(blacklist_key, True, timeout=3600)  # 1 hour blacklist
        
        logger.error(f"Security threat detected from {ip_address}: {threat_type}")
    
    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent is suspicious"""
        if not user_agent:
            return True
        
        suspicious_agents = [
            'sqlmap', 'nikto', 'nmap', 'masscan', 'burpsuite',
            'owasp zap', 'w3af', 'skipfish', 'wpscan',
            'python-requests', 'curl', 'wget'
        ]
        
        user_agent_lower = user_agent.lower()
        return any(agent in user_agent_lower for agent in suspicious_agents)


class EnhancedAuditMiddleware(MiddlewareMixin):
    """
    Enhanced audit logging with compliance features
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.sensitive_fields = {
            'password', 'token', 'secret', 'key', 'api_key',
            'credit_card', 'ssn', 'social_security',
        }
        
        # PII patterns
        self.pii_patterns = {
            'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'phone': r'\+?1?\d{9,15}',
            'ssn': r'\d{3}-\d{2}-\d{4}',
            'credit_card': r'\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}',
        }
    
    def process_request(self, request):
        """Store request start time for performance tracking"""
        request._audit_start_time = time.time()
        request._audit_request_size = len(request.body) if hasattr(request, 'body') else 0
        return None
    
    def process_response(self, request, response):
        """Enhanced audit logging"""
        if self._should_log_request(request, response):
            try:
                self._create_enhanced_audit_log(request, response)
            except Exception as e:
                logger.error(f"Failed to create enhanced audit log: {e}")
        
        return response
    
    def _should_log_request(self, request, response) -> bool:
        """Determine if request should be logged"""
        # Always log API requests
        if request.path.startswith('/api/'):
            return True
        
        # Log sensitive operations
        sensitive_paths = [
            '/admin/', '/auth/', '/login/', '/logout/',
            '/password/', '/mfa/', '/settings/',
        ]
        
        if any(request.path.startswith(path) for path in sensitive_paths):
            return True
        
        # Log failed requests
        if response.status_code >= 400:
            return True
        
        # Log POST/PUT/PATCH/DELETE requests
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return True
        
        return False
    
    def _create_enhanced_audit_log(self, request, response):
        """Create comprehensive audit log entry"""
        from .models import AuditLog
        
        user = getattr(request, 'user', None) if hasattr(request, 'user') else None
        if user and not user.is_authenticated:
            user = None
        
        organization = getattr(request, 'organization', None)
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Calculate response metrics
        response_time = None
        if hasattr(request, '_audit_start_time'):
            response_time = time.time() - request._audit_start_time
        
        request_size = getattr(request, '_audit_request_size', 0)
        response_size = len(response.content) if hasattr(response, 'content') else 0
        
        # Determine action and risk level
        action = self._get_action_description(request, response)
        risk_level = self._calculate_risk_level(request, response, user)
        
        # Extract and sanitize changes
        changes = self._extract_changes(request, response)
        
        # Detect PII in request/response
        pii_detected = self._detect_pii(changes)
        
        # Create audit log
        audit_data = {
            'user': user,
            'organization': organization,
            'action': action,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'changes': changes,
        }
        
        # Add compliance metadata
        audit_data['changes'].update({
            'compliance': {
                'pii_detected': pii_detected,
                'risk_level': risk_level,
                'response_time_ms': round(response_time * 1000, 2) if response_time else None,
                'request_size_bytes': request_size,
                'response_size_bytes': response_size,
                'classification': self._classify_operation(request),
            }
        })
        
        AuditLog.objects.create(**audit_data)
        
        # Additional logging for high-risk operations
        if risk_level == 'high':
            SecurityEvent.log_event(
                'policy_violation',
                user=user,
                organization=organization,
                description=f'High-risk operation: {action}',
                severity='high',
                ip_address=ip_address,
                metadata={
                    'audit_details': changes,
                    'classification': self._classify_operation(request),
                }
            )
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    
    def _get_action_description(self, request, response) -> str:
        """Get detailed action description"""
        method = request.method
        path = request.path
        status = response.status_code
        
        # API operations
        if path.startswith('/api/'):
            if method == 'GET':
                return f"API_READ_{status}"
            elif method == 'POST':
                return f"API_CREATE_{status}"
            elif method == 'PUT':
                return f"API_UPDATE_{status}"
            elif method == 'PATCH':
                return f"API_PARTIAL_UPDATE_{status}"
            elif method == 'DELETE':
                return f"API_DELETE_{status}"
        
        # Authentication operations
        if 'login' in path:
            return f"LOGIN_ATTEMPT_{status}"
        elif 'logout' in path:
            return f"LOGOUT_{status}"
        elif 'mfa' in path:
            return f"MFA_OPERATION_{status}"
        
        # Data operations
        if 'export' in path:
            return f"DATA_EXPORT_{status}"
        elif 'import' in path:
            return f"DATA_IMPORT_{status}"
        
        return f"{method}_{status}"
    
    def _calculate_risk_level(self, request, response, user) -> str:
        """Calculate operation risk level"""
        risk_score = 0
        
        # Base risk by method
        method_risk = {
            'GET': 1, 'POST': 3, 'PUT': 4, 'PATCH': 3, 'DELETE': 5
        }
        risk_score += method_risk.get(request.method, 1)
        
        # Path-based risk
        if any(path in request.path for path in ['/admin/', '/settings/', '/users/']):
            risk_score += 3
        
        if any(path in request.path for path in ['/export/', '/delete/', '/drop/']):
            risk_score += 4
        
        # User-based risk
        if not user or not user.is_authenticated:
            risk_score += 2
        
        # Response-based risk
        if response.status_code >= 400:
            risk_score += 2
        
        # Time-based risk (off-hours operations)
        current_hour = datetime.now().hour
        if current_hour < 6 or current_hour > 22:  # Outside business hours
            risk_score += 1
        
        # Determine risk level
        if risk_score >= 8:
            return 'high'
        elif risk_score >= 5:
            return 'medium'
        else:
            return 'low'
    
    def _extract_changes(self, request, response) -> dict:
        """Extract and sanitize request/response changes"""
        changes = {
            'request': {
                'method': request.method,
                'path': request.path,
                'timestamp': timezone.now().isoformat(),
            },
            'response': {
                'status_code': response.status_code,
                'content_type': response.get('Content-Type', ''),
            }
        }
        
        # Add request data (sanitized)
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if hasattr(request, 'data'):
                    # DRF request
                    request_data = dict(request.data)
                elif hasattr(request, 'body') and request.body:
                    # Raw request
                    content_type = request.META.get('CONTENT_TYPE', '')
                    if 'application/json' in content_type:
                        request_data = json.loads(request.body.decode('utf-8'))
                    else:
                        request_data = dict(request.POST)
                else:
                    request_data = {}
                
                # Sanitize sensitive data
                sanitized_data = self._sanitize_sensitive_data(request_data)
                changes['request']['data'] = sanitized_data
                
            except Exception as e:
                changes['request']['data_error'] = str(e)
        
        return changes
    
    def _sanitize_sensitive_data(self, data) -> dict:
        """Remove or mask sensitive data"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                key_lower = key.lower()
                if any(field in key_lower for field in self.sensitive_fields):
                    sanitized[key] = '[REDACTED]'
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_sensitive_data(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_sensitive_data(item) for item in data]
        else:
            return data
    
    def _detect_pii(self, data) -> List[str]:
        """Detect PII in data"""
        pii_found = []
        data_str = json.dumps(data)
        
        for pii_type, pattern in self.pii_patterns.items():
            if re.search(pattern, data_str, re.IGNORECASE):
                pii_found.append(pii_type)
        
        return pii_found
    
    def _classify_operation(self, request) -> str:
        """Classify operation type for compliance"""
        path = request.path.lower()
        method = request.method
        
        # Data operations
        if 'export' in path or 'download' in path:
            return 'data_export'
        elif 'import' in path or 'upload' in path:
            return 'data_import'
        elif method == 'DELETE':
            return 'data_deletion'
        
        # User operations
        elif '/users/' in path or '/accounts/' in path:
            return 'user_management'
        elif '/auth/' in path or '/login' in path:
            return 'authentication'
        
        # Business operations
        elif '/pricing/' in path or '/quotes/' in path:
            return 'pricing_data'
        elif '/suppliers/' in path:
            return 'supplier_data'
        elif '/materials/' in path:
            return 'material_data'
        
        # System operations
        elif '/admin/' in path or '/settings/' in path:
            return 'system_administration'
        
        return 'general'


class ComplianceMiddleware(MiddlewareMixin):
    """
    GDPR, CCPA, and SOC 2 compliance middleware
    """
    
    def process_request(self, request):
        """Process request for compliance requirements"""
        
        # Check for data subject requests (GDPR/CCPA)
        if self._is_data_subject_request(request):
            self._handle_data_subject_request(request)
        
        # Check for geographic restrictions
        if self._has_geographic_restrictions(request):
            country_code = self._get_country_from_ip(request)
            if not self._is_country_allowed(country_code):
                logger.warning(f"Blocked request from restricted country: {country_code}")
                return JsonResponse({
                    'error': 'Access not available in your region',
                    'code': 'GEOGRAPHIC_RESTRICTION'
                }, status=403)
        
        return None
    
    def _is_data_subject_request(self, request) -> bool:
        """Check if this is a data subject rights request"""
        data_subject_paths = [
            '/api/v1/privacy/export/',
            '/api/v1/privacy/delete/',
            '/api/v1/privacy/rectify/',
            '/api/v1/privacy/portability/',
        ]
        
        return any(request.path.startswith(path) for path in data_subject_paths)
    
    def _handle_data_subject_request(self, request):
        """Handle data subject rights requests"""
        # Log the request
        SecurityEvent.log_event(
            'data_subject_request',
            user=getattr(request, 'user', None) if hasattr(request, 'user') else None,
            description=f'Data subject request: {request.path}',
            severity='medium',
            ip_address=self._get_client_ip(request),
            metadata={
                'request_type': self._get_data_subject_request_type(request.path),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            }
        )
    
    def _get_data_subject_request_type(self, path: str) -> str:
        """Get the type of data subject request"""
        if 'export' in path:
            return 'data_portability'
        elif 'delete' in path:
            return 'right_to_erasure'
        elif 'rectify' in path:
            return 'rectification'
        else:
            return 'access'
    
    def _has_geographic_restrictions(self, request) -> bool:
        """Check if request has geographic restrictions"""
        # Check if any data being accessed has geographic restrictions
        return False  # Implement based on your data classification
    
    def _get_country_from_ip(self, request) -> str:
        """Get country code from IP address"""
        # This would integrate with a GeoIP service
        return 'US'  # Default fallback
    
    def _is_country_allowed(self, country_code: str) -> bool:
        """Check if country is allowed"""
        restricted_countries = getattr(settings, 'RESTRICTED_COUNTRIES', [])
        return country_code not in restricted_countries
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class DataEncryptionMiddleware(MiddlewareMixin):
    """
    Middleware to handle automatic data encryption/decryption
    """
    
    def process_response(self, request, response):
        """Encrypt sensitive data in responses"""
        
        # Only process JSON responses
        if not response.get('Content-Type', '').startswith('application/json'):
            return response
        
        # Only encrypt for API endpoints
        if not request.path.startswith('/api/'):
            return response
        
        try:
            if hasattr(response, 'data') and isinstance(response.data, dict):
                # DRF response
                encrypted_data = self._encrypt_sensitive_fields(response.data)
                response.data = encrypted_data
            
        except Exception as e:
            logger.error(f"Error encrypting response data: {e}")
        
        return response
    
    def _encrypt_sensitive_fields(self, data) -> dict:
        """Encrypt sensitive fields in response data"""
        from .security import crypto_service
        
        sensitive_fields = [
            'ssn', 'tax_id', 'credit_card', 'bank_account',
            'pricing_formula', 'cost_breakdown'
        ]
        
        if isinstance(data, dict):
            encrypted = {}
            for key, value in data.items():
                if key.lower() in sensitive_fields and isinstance(value, str):
                    encrypted[key] = {
                        'encrypted': True,
                        'value': crypto_service.encrypt_sensitive_data(value, f"field_{key}")
                    }
                elif isinstance(value, (dict, list)):
                    encrypted[key] = self._encrypt_sensitive_fields(value)
                else:
                    encrypted[key] = value
            return encrypted
        elif isinstance(data, list):
            return [self._encrypt_sensitive_fields(item) for item in data]
        else:
            return data