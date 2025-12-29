#!/usr/bin/env python3
"""
Comprehensive Security Testing and Vulnerability Scanner
Automated security assessment for AI Pricing Agent
"""
import os
import sys
import json
import asyncio
import logging
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
import aiohttp
from urllib.parse import urljoin, urlparse
import ssl
import socket
import re
from packaging import version

# Add Django project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings.base')

import django
django.setup()

from django.conf import settings
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.core.security_models import SecurityEvent

logger = logging.getLogger(__name__)


@dataclass
class VulnerabilityFinding:
    """Represents a security vulnerability finding"""
    id: str
    title: str
    severity: str  # critical, high, medium, low, info
    category: str
    description: str
    location: str
    evidence: str
    remediation: str
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None
    references: List[str] = None
    
    def __post_init__(self):
        if self.references is None:
            self.references = []


@dataclass
class SecurityScanResult:
    """Results of security scan"""
    scan_id: str
    timestamp: str
    scan_type: str
    target: str
    duration_seconds: float
    findings: List[VulnerabilityFinding]
    summary: Dict[str, int]
    
    def to_dict(self):
        return {
            'scan_id': self.scan_id,
            'timestamp': self.timestamp,
            'scan_type': self.scan_type,
            'target': self.target,
            'duration_seconds': self.duration_seconds,
            'findings': [asdict(f) for f in self.findings],
            'summary': self.summary
        }


class DependencyScanner:
    """Scanner for dependency vulnerabilities"""
    
    def __init__(self):
        self.findings = []
    
    async def scan(self, requirements_file: str = "requirements.txt") -> List[VulnerabilityFinding]:
        """Scan Python dependencies for known vulnerabilities"""
        self.findings = []
        
        # Check if safety is available
        try:
            result = subprocess.run(['safety', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                await self._install_safety()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            await self._install_safety()
        
        # Run safety check
        try:
            cmd = ['safety', 'check', '--json', '--file', requirements_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # No vulnerabilities found
                return self.findings
            
            if result.stderr and "vulnerabilities found" in result.stderr:
                # Parse safety output
                vulnerabilities = json.loads(result.stdout)
                for vuln in vulnerabilities:
                    finding = VulnerabilityFinding(
                        id=f"DEP-{vuln['id']}",
                        title=f"Vulnerable dependency: {vuln['package_name']}",
                        severity=self._map_safety_severity(vuln.get('severity', 'medium')),
                        category="Vulnerable Dependencies",
                        description=vuln['advisory'],
                        location=f"{vuln['package_name']}=={vuln['installed_version']}",
                        evidence=f"Vulnerable version: {vuln['installed_version']}, "
                                f"Safe versions: {', '.join(vuln['safe_versions'])}",
                        remediation=f"Update {vuln['package_name']} to a safe version: "
                                  f"{', '.join(vuln['safe_versions'])}",
                        cwe_id="CWE-1104",  # Use of Unmaintained Third Party Components
                    )
                    self.findings.append(finding)
            
        except Exception as e:
            logger.error(f"Dependency scan failed: {e}")
            self.findings.append(VulnerabilityFinding(
                id="DEP-ERROR",
                title="Dependency scan failed",
                severity="medium",
                category="Scanner Error",
                description=f"Failed to scan dependencies: {str(e)}",
                location=requirements_file,
                evidence=str(e),
                remediation="Check dependency scanner configuration"
            ))
        
        return self.findings
    
    async def _install_safety(self):
        """Install safety scanner"""
        try:
            subprocess.run(['pip', 'install', 'safety'], 
                          capture_output=True, timeout=60)
        except Exception as e:
            logger.error(f"Failed to install safety: {e}")
    
    def _map_safety_severity(self, safety_severity: str) -> str:
        """Map safety severity to our severity levels"""
        mapping = {
            'high': 'high',
            'medium': 'medium', 
            'low': 'low'
        }
        return mapping.get(safety_severity.lower(), 'medium')


class StaticCodeAnalyzer:
    """Static code analysis for security issues"""
    
    def __init__(self):
        self.findings = []
        # Security patterns to look for
        self.security_patterns = {
            'hardcoded_secrets': [
                r'password\s*=\s*["\'][^"\']{8,}["\']',
                r'secret\s*=\s*["\'][^"\']{20,}["\']',
                r'api[_-]?key\s*=\s*["\'][^"\']{20,}["\']',
                r'token\s*=\s*["\'][^"\']{20,}["\']',
            ],
            'sql_injection': [
                r'\.raw\s*\(\s*["\'][^"\']*%s[^"\']*["\']',
                r'\.extra\s*\(\s*where=\s*\[["\'][^"\']*%s[^"\']*["\']\]',
                r'cursor\.execute\s*\(\s*["\'][^"\']*%s[^"\']*["\']',
            ],
            'xss_vulnerabilities': [
                r'\|safe\b',
                r'mark_safe\s*\(',
                r'Markup\s*\(',
                r'autoescape\s+off',
            ],
            'debug_code': [
                r'print\s*\(',
                r'pdb\.set_trace\(\)',
                r'import\s+pdb',
                r'DEBUG\s*=\s*True',
            ],
            'insecure_random': [
                r'random\.random\(\)',
                r'random\.randint\(',
                r'random\.choice\(',
            ],
            'weak_crypto': [
                r'md5\(\)',
                r'sha1\(\)',
                r'DES\.',
                r'RC4\.',
            ]
        }
    
    async def scan(self, source_dir: str = ".") -> List[VulnerabilityFinding]:
        """Scan source code for security issues"""
        self.findings = []
        
        # Get all Python files
        python_files = []
        for root, dirs, files in os.walk(source_dir):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.venv', 'venv']]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        # Scan each file
        for file_path in python_files:
            await self._scan_file(file_path)
        
        # Run bandit if available
        await self._run_bandit(source_dir)
        
        return self.findings
    
    async def _scan_file(self, file_path: str):
        """Scan a single file for security issues"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            for category, patterns in self.security_patterns.items():
                for pattern in patterns:
                    for line_num, line in enumerate(lines, 1):
                        matches = re.finditer(pattern, line, re.IGNORECASE)
                        for match in matches:
                            finding = VulnerabilityFinding(
                                id=f"STATIC-{category.upper()}-{hash(file_path + str(line_num))}",
                                title=self._get_pattern_title(category),
                                severity=self._get_pattern_severity(category),
                                category="Static Code Analysis",
                                description=self._get_pattern_description(category),
                                location=f"{file_path}:{line_num}",
                                evidence=f"Line {line_num}: {line.strip()}",
                                remediation=self._get_pattern_remediation(category),
                                cwe_id=self._get_pattern_cwe(category)
                            )
                            self.findings.append(finding)
        
        except Exception as e:
            logger.error(f"Failed to scan file {file_path}: {e}")
    
    async def _run_bandit(self, source_dir: str):
        """Run bandit security scanner"""
        try:
            # Check if bandit is available
            result = subprocess.run(['bandit', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                await self._install_bandit()
            
            # Run bandit
            cmd = ['bandit', '-r', source_dir, '-f', 'json', '-ll']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.stdout:
                bandit_results = json.loads(result.stdout)
                for issue in bandit_results.get('results', []):
                    finding = VulnerabilityFinding(
                        id=f"BANDIT-{issue['test_id']}",
                        title=issue['test_name'],
                        severity=issue['issue_severity'].lower(),
                        category="Static Code Analysis",
                        description=issue['issue_text'],
                        location=f"{issue['filename']}:{issue['line_number']}",
                        evidence=issue['code'],
                        remediation=self._get_bandit_remediation(issue['test_id']),
                        cwe_id=issue.get('cwe', {}).get('id') if issue.get('cwe') else None
                    )
                    self.findings.append(finding)
        
        except Exception as e:
            logger.error(f"Bandit scan failed: {e}")
    
    async def _install_bandit(self):
        """Install bandit scanner"""
        try:
            subprocess.run(['pip', 'install', 'bandit'], 
                          capture_output=True, timeout=60)
        except Exception as e:
            logger.error(f"Failed to install bandit: {e}")
    
    def _get_pattern_title(self, category: str) -> str:
        """Get title for pattern category"""
        titles = {
            'hardcoded_secrets': 'Hardcoded Secret',
            'sql_injection': 'Potential SQL Injection',
            'xss_vulnerabilities': 'XSS Vulnerability',
            'debug_code': 'Debug Code in Production',
            'insecure_random': 'Insecure Random Number Generation',
            'weak_crypto': 'Weak Cryptographic Algorithm'
        }
        return titles.get(category, 'Security Issue')
    
    def _get_pattern_severity(self, category: str) -> str:
        """Get severity for pattern category"""
        severities = {
            'hardcoded_secrets': 'high',
            'sql_injection': 'critical',
            'xss_vulnerabilities': 'high',
            'debug_code': 'medium',
            'insecure_random': 'medium',
            'weak_crypto': 'high'
        }
        return severities.get(category, 'medium')
    
    def _get_pattern_description(self, category: str) -> str:
        """Get description for pattern category"""
        descriptions = {
            'hardcoded_secrets': 'Hardcoded secrets in source code pose security risks',
            'sql_injection': 'Raw SQL queries may be vulnerable to injection attacks',
            'xss_vulnerabilities': 'Unescaped output may allow XSS attacks',
            'debug_code': 'Debug code should not be present in production',
            'insecure_random': 'Standard random functions are not cryptographically secure',
            'weak_crypto': 'Weak cryptographic algorithms should not be used'
        }
        return descriptions.get(category, 'Security vulnerability detected')
    
    def _get_pattern_remediation(self, category: str) -> str:
        """Get remediation for pattern category"""
        remediations = {
            'hardcoded_secrets': 'Use environment variables or secure secret management',
            'sql_injection': 'Use parameterized queries or ORM methods',
            'xss_vulnerabilities': 'Properly escape output or use Django template auto-escaping',
            'debug_code': 'Remove debug code before deployment',
            'insecure_random': 'Use secrets module for cryptographic operations',
            'weak_crypto': 'Use strong cryptographic algorithms (SHA-256, AES-256)'
        }
        return remediations.get(category, 'Fix the security issue')
    
    def _get_pattern_cwe(self, category: str) -> str:
        """Get CWE ID for pattern category"""
        cwes = {
            'hardcoded_secrets': 'CWE-798',
            'sql_injection': 'CWE-89',
            'xss_vulnerabilities': 'CWE-79',
            'debug_code': 'CWE-489',
            'insecure_random': 'CWE-338',
            'weak_crypto': 'CWE-327'
        }
        return cwes.get(category)
    
    def _get_bandit_remediation(self, test_id: str) -> str:
        """Get remediation advice for bandit test ID"""
        remediations = {
            'B101': 'Avoid using assert statements in production code',
            'B102': 'Use secure methods instead of exec',
            'B103': 'Set file permissions appropriately',
            'B104': 'Avoid binding to all interfaces',
            'B105': 'Use strong password hashing algorithms',
            'B106': 'Avoid hardcoded passwords',
            'B107': 'Avoid hardcoded passwords in function defaults',
            'B108': 'Use secure temporary file creation methods',
            'B110': 'Avoid try/except/pass patterns',
            'B112': 'Use secure XML parsers',
        }
        return remediations.get(test_id, 'Follow secure coding practices')


class WebApplicationScanner:
    """Web application security scanner"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.findings = []
        self.session = None
    
    async def scan(self) -> List[VulnerabilityFinding]:
        """Perform web application security scan"""
        self.findings = []
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(ssl=False)  # For testing
        ) as session:
            self.session = session
            
            # Basic connectivity test
            await self._test_connectivity()
            
            # Security headers test
            await self._test_security_headers()
            
            # SSL/TLS test
            await self._test_ssl_configuration()
            
            # Authentication tests
            await self._test_authentication()
            
            # CSRF protection test
            await self._test_csrf_protection()
            
            # Input validation tests
            await self._test_input_validation()
            
            # Error handling test
            await self._test_error_handling()
        
        return self.findings
    
    async def _test_connectivity(self):
        """Test basic connectivity and response"""
        try:
            async with self.session.get(self.base_url) as response:
                if response.status == 200:
                    logger.info(f"Successfully connected to {self.base_url}")
                else:
                    self.findings.append(VulnerabilityFinding(
                        id="WEB-CONNECTIVITY",
                        title="Connectivity Issue",
                        severity="info",
                        category="Web Application",
                        description=f"Unexpected response status: {response.status}",
                        location=self.base_url,
                        evidence=f"HTTP {response.status}",
                        remediation="Check application availability"
                    ))
        except Exception as e:
            self.findings.append(VulnerabilityFinding(
                id="WEB-CONNECTION-FAILED",
                title="Connection Failed",
                severity="high",
                category="Web Application",
                description=f"Failed to connect to application: {str(e)}",
                location=self.base_url,
                evidence=str(e),
                remediation="Check application availability and network connectivity"
            ))
    
    async def _test_security_headers(self):
        """Test for security headers"""
        try:
            async with self.session.get(self.base_url) as response:
                headers = response.headers
                
                # Required security headers
                required_headers = {
                    'X-Content-Type-Options': 'nosniff',
                    'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
                    'X-XSS-Protection': '1; mode=block',
                    'Strict-Transport-Security': None,  # Should exist if HTTPS
                    'Content-Security-Policy': None,
                }
                
                for header, expected_value in required_headers.items():
                    if header not in headers:
                        self.findings.append(VulnerabilityFinding(
                            id=f"WEB-HEADER-{header.upper().replace('-', '_')}",
                            title=f"Missing Security Header: {header}",
                            severity="medium",
                            category="Web Application",
                            description=f"Security header {header} is missing",
                            location=self.base_url,
                            evidence=f"Response headers: {dict(headers)}",
                            remediation=f"Add {header} security header"
                        ))
                    elif expected_value and headers.get(header) not in expected_value:
                        if isinstance(expected_value, list):
                            self.findings.append(VulnerabilityFinding(
                                id=f"WEB-HEADER-{header.upper().replace('-', '_')}_VALUE",
                                title=f"Insecure Security Header: {header}",
                                severity="low",
                                category="Web Application", 
                                description=f"Security header {header} has insecure value",
                                location=self.base_url,
                                evidence=f"{header}: {headers.get(header)}",
                                remediation=f"Set {header} to one of: {', '.join(expected_value)}"
                            ))
                
                # Check for information disclosure headers
                info_headers = ['Server', 'X-Powered-By']
                for header in info_headers:
                    if header in headers:
                        self.findings.append(VulnerabilityFinding(
                            id=f"WEB-INFO-{header.upper().replace('-', '_')}",
                            title=f"Information Disclosure: {header}",
                            severity="low",
                            category="Web Application",
                            description=f"Server information disclosed in {header} header",
                            location=self.base_url,
                            evidence=f"{header}: {headers.get(header)}",
                            remediation=f"Remove or obfuscate {header} header"
                        ))
        
        except Exception as e:
            logger.error(f"Security headers test failed: {e}")
    
    async def _test_ssl_configuration(self):
        """Test SSL/TLS configuration"""
        if not self.base_url.startswith('https://'):
            self.findings.append(VulnerabilityFinding(
                id="WEB-SSL-NOT-USED",
                title="HTTPS Not Used",
                severity="high",
                category="Web Application",
                description="Application is not using HTTPS",
                location=self.base_url,
                evidence="URL scheme is HTTP",
                remediation="Configure HTTPS with valid SSL certificate"
            ))
            return
        
        try:
            # Parse hostname from URL
            hostname = urlparse(self.base_url).hostname
            
            # Test SSL configuration
            context = ssl.create_default_context()
            
            with socket.create_connection((hostname, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    
                    # Check certificate validity
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    if not_after < datetime.now():
                        self.findings.append(VulnerabilityFinding(
                            id="WEB-SSL-EXPIRED",
                            title="SSL Certificate Expired",
                            severity="critical",
                            category="Web Application",
                            description="SSL certificate has expired",
                            location=hostname,
                            evidence=f"Certificate expired on: {cert['notAfter']}",
                            remediation="Renew SSL certificate"
                        ))
                    
                    # Check cipher strength
                    if cipher and cipher[1] < 256:  # Key length less than 256 bits
                        self.findings.append(VulnerabilityFinding(
                            id="WEB-SSL-WEAK-CIPHER",
                            title="Weak SSL Cipher",
                            severity="medium",
                            category="Web Application",
                            description="Weak SSL cipher in use",
                            location=hostname,
                            evidence=f"Cipher: {cipher}",
                            remediation="Configure strong SSL ciphers (256-bit or higher)"
                        ))
        
        except Exception as e:
            logger.error(f"SSL test failed: {e}")
    
    async def _test_authentication(self):
        """Test authentication mechanisms"""
        auth_endpoints = [
            '/api/v1/auth/login/',
            '/auth/login/',
            '/login/',
            '/admin/login/',
        ]
        
        for endpoint in auth_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                async with self.session.get(url) as response:
                    if response.status == 200:
                        # Test for rate limiting
                        await self._test_rate_limiting(url)
                        
                        # Test for account lockout
                        await self._test_account_lockout(url)
            
            except Exception as e:
                logger.debug(f"Auth endpoint {endpoint} not accessible: {e}")
    
    async def _test_rate_limiting(self, login_url: str):
        """Test rate limiting on authentication"""
        try:
            # Make multiple rapid requests
            responses = []
            for i in range(20):
                async with self.session.post(login_url, data={
                    'username': 'testuser',
                    'password': 'testpass'
                }) as response:
                    responses.append(response.status)
            
            # Check if rate limiting is in effect
            if all(status != 429 for status in responses[-5:]):  # Last 5 responses
                self.findings.append(VulnerabilityFinding(
                    id="WEB-NO-RATE-LIMIT",
                    title="No Rate Limiting on Authentication",
                    severity="medium",
                    category="Web Application",
                    description="Authentication endpoint lacks rate limiting",
                    location=login_url,
                    evidence="Multiple rapid authentication attempts allowed",
                    remediation="Implement rate limiting on authentication endpoints"
                ))
        
        except Exception as e:
            logger.error(f"Rate limiting test failed: {e}")
    
    async def _test_account_lockout(self, login_url: str):
        """Test account lockout mechanisms"""
        # This would require valid test accounts and is environment-specific
        # Placeholder for more sophisticated testing
        pass
    
    async def _test_csrf_protection(self):
        """Test CSRF protection"""
        try:
            # Try to access a form endpoint
            form_endpoints = [
                '/api/v1/users/',
                '/admin/',
                '/settings/',
            ]
            
            for endpoint in form_endpoints:
                try:
                    url = urljoin(self.base_url, endpoint)
                    
                    # GET request to get form
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            
                            # Check for CSRF token
                            if 'csrfmiddlewaretoken' not in content.lower():
                                self.findings.append(VulnerabilityFinding(
                                    id=f"WEB-CSRF-{endpoint.replace('/', '_')}",
                                    title="Missing CSRF Protection",
                                    severity="medium",
                                    category="Web Application",
                                    description="Form lacks CSRF protection",
                                    location=url,
                                    evidence="No CSRF token found in form",
                                    remediation="Implement CSRF protection"
                                ))
                
                except Exception as e:
                    logger.debug(f"CSRF test failed for {endpoint}: {e}")
        
        except Exception as e:
            logger.error(f"CSRF protection test failed: {e}")
    
    async def _test_input_validation(self):
        """Test input validation"""
        # Test common injection payloads
        payloads = {
            'xss': ["<script>alert('XSS')</script>", "javascript:alert('XSS')"],
            'sql': ["' OR '1'='1", "'; DROP TABLE users; --"],
            'command': ["; cat /etc/passwd", "| whoami"],
        }
        
        test_endpoints = [
            '/api/v1/search/',
            '/search/',
        ]
        
        for endpoint in test_endpoints:
            for attack_type, attack_payloads in payloads.items():
                for payload in attack_payloads:
                    try:
                        url = urljoin(self.base_url, endpoint)
                        params = {'q': payload}
                        
                        async with self.session.get(url, params=params) as response:
                            content = await response.text()
                            
                            # Check if payload is reflected unescaped
                            if payload in content and response.headers.get('content-type', '').startswith('text/html'):
                                self.findings.append(VulnerabilityFinding(
                                    id=f"WEB-{attack_type.upper()}-{hash(endpoint + payload)}",
                                    title=f"Potential {attack_type.upper()} Vulnerability",
                                    severity="high" if attack_type in ['xss', 'sql'] else "medium",
                                    category="Web Application",
                                    description=f"Input validation bypass detected for {attack_type}",
                                    location=url,
                                    evidence=f"Payload '{payload}' reflected in response",
                                    remediation="Implement proper input validation and output encoding"
                                ))
                    
                    except Exception as e:
                        logger.debug(f"Input validation test failed: {e}")
    
    async def _test_error_handling(self):
        """Test error handling for information disclosure"""
        error_endpoints = [
            '/nonexistent-page-12345',
            '/api/v1/nonexistent/',
            '/admin/nonexistent/',
        ]
        
        for endpoint in error_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                async with self.session.get(url) as response:
                    if response.status in [404, 500]:
                        content = await response.text()
                        
                        # Check for stack traces or sensitive information
                        sensitive_patterns = [
                            r'Traceback \(most recent call last\)',
                            r'File "/.+\.py"',
                            r'DEBUG = True',
                            r'SECRET_KEY',
                            r'Database.*error',
                        ]
                        
                        for pattern in sensitive_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                self.findings.append(VulnerabilityFinding(
                                    id="WEB-INFO-DISCLOSURE",
                                    title="Information Disclosure in Error Pages",
                                    severity="medium",
                                    category="Web Application",
                                    description="Error pages disclose sensitive information",
                                    location=url,
                                    evidence=f"Pattern found: {pattern}",
                                    remediation="Configure custom error pages without sensitive information"
                                ))
                                break
            
            except Exception as e:
                logger.debug(f"Error handling test failed for {endpoint}: {e}")


class SecurityScanOrchestrator:
    """Orchestrates comprehensive security scanning"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.scan_id = f"security_scan_{int(datetime.now().timestamp())}"
    
    async def run_comprehensive_scan(self, target_url: str = None, 
                                   source_dir: str = ".") -> SecurityScanResult:
        """Run comprehensive security scan"""
        start_time = datetime.now()
        all_findings = []
        
        logger.info(f"Starting comprehensive security scan: {self.scan_id}")
        
        # Dependency scan
        logger.info("Running dependency vulnerability scan...")
        dep_scanner = DependencyScanner()
        dep_findings = await dep_scanner.scan()
        all_findings.extend(dep_findings)
        logger.info(f"Dependency scan found {len(dep_findings)} issues")
        
        # Static code analysis
        logger.info("Running static code analysis...")
        static_analyzer = StaticCodeAnalyzer()
        static_findings = await static_analyzer.scan(source_dir)
        all_findings.extend(static_findings)
        logger.info(f"Static analysis found {len(static_findings)} issues")
        
        # Web application scan
        if target_url:
            logger.info(f"Running web application scan on {target_url}...")
            web_scanner = WebApplicationScanner(target_url)
            web_findings = await web_scanner.scan()
            all_findings.extend(web_findings)
            logger.info(f"Web application scan found {len(web_findings)} issues")
        
        # Calculate summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        summary = {
            'critical': len([f for f in all_findings if f.severity == 'critical']),
            'high': len([f for f in all_findings if f.severity == 'high']),
            'medium': len([f for f in all_findings if f.severity == 'medium']),
            'low': len([f for f in all_findings if f.severity == 'low']),
            'info': len([f for f in all_findings if f.severity == 'info']),
            'total': len(all_findings),
        }
        
        result = SecurityScanResult(
            scan_id=self.scan_id,
            timestamp=start_time.isoformat(),
            scan_type="comprehensive",
            target=target_url or source_dir,
            duration_seconds=duration,
            findings=all_findings,
            summary=summary
        )
        
        # Log security scan event
        SecurityEvent.log_event(
            'security_scan',
            description=f'Comprehensive security scan completed: {self.scan_id}',
            severity='medium',
            metadata={
                'scan_id': self.scan_id,
                'findings_summary': summary,
                'duration_seconds': duration,
            }
        )
        
        logger.info(f"Security scan completed in {duration:.2f} seconds")
        logger.info(f"Found {summary['total']} total issues: "
                   f"{summary['critical']} critical, {summary['high']} high, "
                   f"{summary['medium']} medium, {summary['low']} low")
        
        return result
    
    def save_results(self, result: SecurityScanResult, output_file: str = None):
        """Save scan results to file"""
        if not output_file:
            output_file = f"security_scan_{result.scan_id}.json"
        
        with open(output_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        logger.info(f"Scan results saved to: {output_file}")
        return output_file


async def main():
    """Main function for running security scan"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Comprehensive Security Scanner')
    parser.add_argument('--url', help='Target URL for web application scan')
    parser.add_argument('--source-dir', default='.', help='Source directory for static analysis')
    parser.add_argument('--output', help='Output file for results')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run scan
    orchestrator = SecurityScanOrchestrator()
    result = await orchestrator.run_comprehensive_scan(
        target_url=args.url,
        source_dir=args.source_dir
    )
    
    # Save results
    output_file = orchestrator.save_results(result, args.output)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"SECURITY SCAN SUMMARY")
    print(f"{'='*60}")
    print(f"Scan ID: {result.scan_id}")
    print(f"Duration: {result.duration_seconds:.2f} seconds")
    print(f"Target: {result.target}")
    print(f"\nFindings by Severity:")
    for severity, count in result.summary.items():
        if severity != 'total' and count > 0:
            print(f"  {severity.upper()}: {count}")
    print(f"\nTotal Issues: {result.summary['total']}")
    print(f"Results saved to: {output_file}")
    
    # Return non-zero exit code if critical or high severity issues found
    if result.summary['critical'] > 0 or result.summary['high'] > 0:
        print(f"\nWARNING: Critical or high-severity security issues found!")
        return 1
    
    return 0


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))