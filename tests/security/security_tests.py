"""
Security testing framework for the AI Pricing Agent system.
"""
import pytest
import requests
import json
import base64
import hashlib
import time
from typing import Dict, List, Any, Optional
from urllib.parse import urlencode, quote
from dataclasses import dataclass


@dataclass
class SecurityTest:
    """Represents a security test case."""
    name: str
    description: str
    category: str  # 'auth', 'injection', 'xss', 'access_control', etc.
    severity: str  # 'critical', 'high', 'medium', 'low'
    payload: Any
    expected_status_codes: List[int]
    should_block: bool = True


class SecurityTestFramework:
    """Framework for automated security testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000", ml_service_url: str = "http://localhost:8001"):
        self.base_url = base_url.rstrip('/')
        self.ml_service_url = ml_service_url.rstrip('/')
        self.session = requests.Session()
        self.test_results = []
        
        # Common headers for testing
        self.common_headers = {
            'User-Agent': 'SecurityTestFramework/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def authenticate(self, username: str = "test@example.com", password: str = "testpass123") -> Optional[str]:
        """Authenticate and return access token."""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login/",
                json={"email": username, "password": password},
                headers=self.common_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                if token:
                    self.session.headers.update({"Authorization": f"Bearer {token}"})
                return token
        except Exception as e:
            print(f"Authentication failed: {e}")
        
        return None
    
    def run_test(self, test: SecurityTest) -> Dict[str, Any]:
        """Run a single security test."""
        print(f"Running: {test.name}")
        
        result = {
            'name': test.name,
            'description': test.description,
            'category': test.category,
            'severity': test.severity,
            'status': 'PASS',
            'details': '',
            'response_status': None,
            'response_body': '',
            'vulnerability_detected': False
        }
        
        try:
            # Execute the test based on category
            if test.category == 'injection':
                response = self._test_injection(test)
            elif test.category == 'xss':
                response = self._test_xss(test)
            elif test.category == 'auth':
                response = self._test_authentication(test)
            elif test.category == 'access_control':
                response = self._test_access_control(test)
            elif test.category == 'input_validation':
                response = self._test_input_validation(test)
            else:
                response = self._generic_test(test)
            
            result['response_status'] = response.status_code
            result['response_body'] = response.text[:500]  # Truncate for readability
            
            # Evaluate test result
            if test.should_block:
                # Test expects the payload to be blocked
                if response.status_code in test.expected_status_codes:
                    result['status'] = 'PASS'
                else:
                    result['status'] = 'FAIL'
                    result['vulnerability_detected'] = True
                    result['details'] = f"Expected blocking (status {test.expected_status_codes}), got {response.status_code}"
            else:
                # Test expects the payload to be allowed
                if response.status_code in test.expected_status_codes:
                    result['status'] = 'PASS'
                else:
                    result['status'] = 'FAIL'
                    result['details'] = f"Expected success (status {test.expected_status_codes}), got {response.status_code}"
        
        except Exception as e:
            result['status'] = 'ERROR'
            result['details'] = str(e)
        
        self.test_results.append(result)
        return result
    
    def _test_injection(self, test: SecurityTest) -> requests.Response:
        """Test for injection vulnerabilities."""
        if isinstance(test.payload, dict) and 'url' in test.payload:
            # URL-based injection test
            url = f"{self.base_url}{test.payload['url']}"
            method = test.payload.get('method', 'GET').upper()
            
            if method == 'GET':
                return self.session.get(url, headers=self.common_headers)
            elif method == 'POST':
                data = test.payload.get('data', {})
                return self.session.post(url, json=data, headers=self.common_headers)
            elif method == 'PUT':
                data = test.payload.get('data', {})
                return self.session.put(url, json=data, headers=self.common_headers)
        
        return self.session.get(f"{self.base_url}/", headers=self.common_headers)
    
    def _test_xss(self, test: SecurityTest) -> requests.Response:
        """Test for XSS vulnerabilities."""
        if isinstance(test.payload, dict):
            url = f"{self.base_url}{test.payload.get('endpoint', '/api/v1/materials/')}"
            xss_payload = test.payload.get('payload', '')
            
            # Test in different contexts
            if 'search' in test.payload.get('endpoint', ''):
                return self.session.get(url, params={'search': xss_payload}, headers=self.common_headers)
            else:
                return self.session.post(url, json={'name': xss_payload}, headers=self.common_headers)
        
        return self.session.get(f"{self.base_url}/", headers=self.common_headers)
    
    def _test_authentication(self, test: SecurityTest) -> requests.Response:
        """Test authentication mechanisms."""
        if isinstance(test.payload, dict):
            url = f"{self.base_url}{test.payload.get('endpoint', '/api/v1/materials/')}"
            
            # Test with various authentication scenarios
            if test.payload.get('no_auth'):
                # Remove authentication
                headers = self.common_headers.copy()
                headers.pop('Authorization', None)
                return requests.get(url, headers=headers)
            
            elif test.payload.get('invalid_token'):
                headers = self.common_headers.copy()
                headers['Authorization'] = 'Bearer invalid_token_12345'
                return requests.get(url, headers=headers)
            
            elif test.payload.get('expired_token'):
                headers = self.common_headers.copy()
                # Use a token that's clearly expired (very old timestamp)
                headers['Authorization'] = 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE1NDY5MzQ0MDB9.invalid'
                return requests.get(url, headers=headers)
        
        return self.session.get(f"{self.base_url}/", headers=self.common_headers)
    
    def _test_access_control(self, test: SecurityTest) -> requests.Response:
        """Test access control mechanisms."""
        if isinstance(test.payload, dict):
            url = f"{self.base_url}{test.payload.get('endpoint', '/api/v1/admin/')}"
            method = test.payload.get('method', 'GET').upper()
            
            if method == 'GET':
                return self.session.get(url, headers=self.common_headers)
            elif method == 'POST':
                return self.session.post(url, json=test.payload.get('data', {}), headers=self.common_headers)
            elif method == 'DELETE':
                return self.session.delete(url, headers=self.common_headers)
        
        return self.session.get(f"{self.base_url}/", headers=self.common_headers)
    
    def _test_input_validation(self, test: SecurityTest) -> requests.Response:
        """Test input validation."""
        if isinstance(test.payload, dict):
            url = f"{self.base_url}{test.payload.get('endpoint', '/api/v1/materials/')}"
            data = test.payload.get('data', {})
            
            return self.session.post(url, json=data, headers=self.common_headers)
        
        return self.session.get(f"{self.base_url}/", headers=self.common_headers)
    
    def _generic_test(self, test: SecurityTest) -> requests.Response:
        """Generic test execution."""
        if isinstance(test.payload, dict) and 'url' in test.payload:
            url = f"{self.base_url}{test.payload['url']}"
            return self.session.get(url, headers=self.common_headers)
        
        return self.session.get(f"{self.base_url}/", headers=self.common_headers)


class SecurityTestSuite:
    """Comprehensive security test suite."""
    
    def __init__(self):
        self.tests = []
        self._define_tests()
    
    def _define_tests(self):
        """Define all security tests."""
        
        # SQL Injection Tests
        sql_injection_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1' UNION SELECT * FROM users --",
            "admin'--",
            "' OR 1=1#",
            "') OR '1'='1--",
            "1' AND (SELECT COUNT(*) FROM users)>0--"
        ]
        
        for payload in sql_injection_payloads:
            self.tests.append(SecurityTest(
                name=f"SQL Injection: {payload[:20]}...",
                description=f"Test SQL injection with payload: {payload}",
                category="injection",
                severity="critical",
                payload={
                    "url": "/api/v1/materials/",
                    "method": "GET",
                    "params": {"search": payload}
                },
                expected_status_codes=[400, 403, 422],
                should_block=True
            ))
        
        # XSS Tests
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "<iframe src=javascript:alert('xss')></iframe>",
            "';alert('xss');//",
            "<script>document.cookie='stolen'</script>"
        ]
        
        for payload in xss_payloads:
            self.tests.append(SecurityTest(
                name=f"XSS: {payload[:20]}...",
                description=f"Test XSS with payload: {payload}",
                category="xss",
                severity="high",
                payload={
                    "endpoint": "/api/v1/materials/",
                    "payload": payload
                },
                expected_status_codes=[400, 403, 422],
                should_block=True
            ))
        
        # Authentication Tests
        auth_tests = [
            {
                "name": "No Authentication Required",
                "payload": {"endpoint": "/api/v1/materials/", "no_auth": True},
                "expected_codes": [401, 403]
            },
            {
                "name": "Invalid Token",
                "payload": {"endpoint": "/api/v1/materials/", "invalid_token": True},
                "expected_codes": [401, 403]
            },
            {
                "name": "Expired Token",
                "payload": {"endpoint": "/api/v1/materials/", "expired_token": True},
                "expected_codes": [401, 403]
            }
        ]
        
        for test in auth_tests:
            self.tests.append(SecurityTest(
                name=test["name"],
                description=f"Test authentication: {test['name']}",
                category="auth",
                severity="critical",
                payload=test["payload"],
                expected_status_codes=test["expected_codes"],
                should_block=True
            ))
        
        # Access Control Tests
        access_control_tests = [
            {
                "name": "Admin Endpoint Access",
                "payload": {"endpoint": "/api/v1/admin/users/", "method": "GET"},
                "expected_codes": [403]
            },
            {
                "name": "User Creation Without Permissions",
                "payload": {
                    "endpoint": "/api/v1/users/",
                    "method": "POST",
                    "data": {"username": "hacker", "email": "hack@test.com"}
                },
                "expected_codes": [403]
            },
            {
                "name": "Delete Other User's Data",
                "payload": {"endpoint": "/api/v1/users/999/", "method": "DELETE"},
                "expected_codes": [403, 404]
            }
        ]
        
        for test in access_control_tests:
            self.tests.append(SecurityTest(
                name=test["name"],
                description=f"Test access control: {test['name']}",
                category="access_control",
                severity="high",
                payload=test["payload"],
                expected_status_codes=test["expected_codes"],
                should_block=True
            ))
        
        # Input Validation Tests
        input_validation_tests = [
            {
                "name": "Oversized Input",
                "data": {"name": "A" * 10000, "description": "Test material"},
                "expected_codes": [400, 413, 422]
            },
            {
                "name": "Invalid Email Format",
                "endpoint": "/api/v1/suppliers/",
                "data": {"name": "Test Supplier", "email": "not-an-email"},
                "expected_codes": [400, 422]
            },
            {
                "name": "Negative Quantity",
                "data": {"name": "Test", "quantity": -100},
                "expected_codes": [400, 422]
            },
            {
                "name": "Invalid Date Format",
                "data": {"name": "Test", "delivery_date": "invalid-date"},
                "expected_codes": [400, 422]
            }
        ]
        
        for test in input_validation_tests:
            self.tests.append(SecurityTest(
                name=test["name"],
                description=f"Test input validation: {test['name']}",
                category="input_validation",
                severity="medium",
                payload={
                    "endpoint": test.get("endpoint", "/api/v1/materials/"),
                    "data": test["data"]
                },
                expected_status_codes=test["expected_codes"],
                should_block=True
            ))
        
        # Path Traversal Tests
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc//passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd"
        ]
        
        for payload in path_traversal_payloads:
            self.tests.append(SecurityTest(
                name=f"Path Traversal: {payload[:20]}...",
                description=f"Test path traversal with payload: {payload}",
                category="injection",
                severity="high",
                payload={
                    "url": f"/api/v1/files/{payload}",
                    "method": "GET"
                },
                expected_status_codes=[400, 403, 404],
                should_block=True
            ))
        
        # Command Injection Tests
        command_injection_payloads = [
            "; ls -la",
            "| whoami",
            "`cat /etc/passwd`",
            "$(cat /etc/passwd)",
            "&& dir",
            "; cat /etc/shadow"
        ]
        
        for payload in command_injection_payloads:
            self.tests.append(SecurityTest(
                name=f"Command Injection: {payload[:20]}...",
                description=f"Test command injection with payload: {payload}",
                category="injection",
                severity="critical",
                payload={
                    "endpoint": "/api/v1/materials/",
                    "data": {"name": f"test{payload}", "description": "test"}
                },
                expected_status_codes=[400, 403, 422],
                should_block=True
            ))
        
        # LDAP Injection Tests
        ldap_injection_payloads = [
            "*)(uid=*",
            "*)(|(uid=*))",
            "*)(&(uid=*)",
            "*))%00"
        ]
        
        for payload in ldap_injection_payloads:
            self.tests.append(SecurityTest(
                name=f"LDAP Injection: {payload}",
                description=f"Test LDAP injection with payload: {payload}",
                category="injection",
                severity="high",
                payload={
                    "endpoint": "/api/v1/users/search/",
                    "method": "GET",
                    "params": {"username": payload}
                },
                expected_status_codes=[400, 403, 422],
                should_block=True
            ))
        
        # Rate Limiting Tests
        self.tests.append(SecurityTest(
            name="Rate Limiting Test",
            description="Test if rate limiting is properly implemented",
            category="rate_limiting",
            severity="medium",
            payload={
                "endpoint": "/api/v1/materials/",
                "method": "GET",
                "rapid_requests": 100
            },
            expected_status_codes=[429],  # Too Many Requests
            should_block=True
        ))


class SecurityTestRunner:
    """Run security tests and generate reports."""
    
    def __init__(self, base_url: str = "http://localhost:8000", ml_service_url: str = "http://localhost:8001"):
        self.framework = SecurityTestFramework(base_url, ml_service_url)
        self.test_suite = SecurityTestSuite()
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all security tests."""
        print("Starting comprehensive security test suite...")
        print(f"Total tests: {len(self.test_suite.tests)}")
        
        # Authenticate first
        token = self.framework.authenticate()
        if not token:
            print("Warning: Authentication failed. Some tests may not run correctly.")
        
        results = {
            'total_tests': len(self.test_suite.tests),
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'vulnerabilities_found': 0,
            'tests': [],
            'summary_by_category': {},
            'summary_by_severity': {}
        }
        
        for test in self.test_suite.tests:
            result = self.framework.run_test(test)
            results['tests'].append(result)
            
            # Update counters
            if result['status'] == 'PASS':
                results['passed'] += 1
            elif result['status'] == 'FAIL':
                results['failed'] += 1
                if result['vulnerability_detected']:
                    results['vulnerabilities_found'] += 1
            else:
                results['errors'] += 1
            
            # Update category summary
            category = result['category']
            if category not in results['summary_by_category']:
                results['summary_by_category'][category] = {'passed': 0, 'failed': 0, 'errors': 0}
            
            if result['status'] == 'PASS':
                results['summary_by_category'][category]['passed'] += 1
            elif result['status'] == 'FAIL':
                results['summary_by_category'][category]['failed'] += 1
            else:
                results['summary_by_category'][category]['errors'] += 1
            
            # Update severity summary
            severity = result['severity']
            if severity not in results['summary_by_severity']:
                results['summary_by_severity'][severity] = {'passed': 0, 'failed': 0, 'errors': 0}
            
            if result['status'] == 'PASS':
                results['summary_by_severity'][severity]['passed'] += 1
            elif result['status'] == 'FAIL':
                results['summary_by_severity'][severity]['failed'] += 1
            else:
                results['summary_by_severity'][severity]['errors'] += 1
        
        return results
    
    def run_tests_by_category(self, category: str) -> Dict[str, Any]:
        """Run tests for a specific category."""
        category_tests = [test for test in self.test_suite.tests if test.category == category]
        
        if not category_tests:
            return {'error': f'No tests found for category: {category}'}
        
        print(f"Running {len(category_tests)} tests for category: {category}")
        
        # Authenticate
        token = self.framework.authenticate()
        
        results = {
            'category': category,
            'total_tests': len(category_tests),
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'vulnerabilities_found': 0,
            'tests': []
        }
        
        for test in category_tests:
            result = self.framework.run_test(test)
            results['tests'].append(result)
            
            if result['status'] == 'PASS':
                results['passed'] += 1
            elif result['status'] == 'FAIL':
                results['failed'] += 1
                if result['vulnerability_detected']:
                    results['vulnerabilities_found'] += 1
            else:
                results['errors'] += 1
        
        return results
    
    def generate_report(self, results: Dict[str, Any], output_file: str = "security_test_report.json"):
        """Generate security test report."""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Generate summary report
        summary_file = output_file.replace('.json', '_summary.txt')
        with open(summary_file, 'w') as f:
            f.write("SECURITY TEST REPORT SUMMARY\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Total Tests: {results['total_tests']}\n")
            f.write(f"Passed: {results['passed']}\n")
            f.write(f"Failed: {results['failed']}\n")
            f.write(f"Errors: {results['errors']}\n")
            f.write(f"Vulnerabilities Found: {results['vulnerabilities_found']}\n\n")
            
            if results['vulnerabilities_found'] > 0:
                f.write("CRITICAL: VULNERABILITIES DETECTED!\n")
                f.write("-" * 40 + "\n")
                
                for test in results['tests']:
                    if test['vulnerability_detected']:
                        f.write(f"• {test['name']} ({test['severity']}): {test['details']}\n")
                f.write("\n")
            
            f.write("Summary by Category:\n")
            f.write("-" * 20 + "\n")
            for category, stats in results['summary_by_category'].items():
                f.write(f"{category}: {stats['passed']} passed, {stats['failed']} failed, {stats['errors']} errors\n")
            
            f.write("\nSummary by Severity:\n")
            f.write("-" * 20 + "\n")
            for severity, stats in results['summary_by_severity'].items():
                f.write(f"{severity}: {stats['passed']} passed, {stats['failed']} failed, {stats['errors']} errors\n")
        
        print(f"Security test report saved to: {output_file}")
        print(f"Summary report saved to: {summary_file}")


def main():
    """Main function for running security tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run security tests")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL for Django app")
    parser.add_argument("--ml-url", default="http://localhost:8001", help="ML service URL")
    parser.add_argument("--category", help="Run tests for specific category")
    parser.add_argument("--output", default="security_test_report.json", help="Output report file")
    
    args = parser.parse_args()
    
    runner = SecurityTestRunner(args.base_url, args.ml_url)
    
    if args.category:
        results = runner.run_tests_by_category(args.category)
    else:
        results = runner.run_all_tests()
    
    runner.generate_report(results, args.output)
    
    # Print summary
    print("\n" + "=" * 50)
    print("SECURITY TEST SUMMARY")
    print("=" * 50)
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Errors: {results['errors']}")
    print(f"Vulnerabilities Found: {results['vulnerabilities_found']}")
    
    if results['vulnerabilities_found'] > 0:
        print(f"\n❌ CRITICAL: {results['vulnerabilities_found']} vulnerabilities detected!")
        print("Please review the detailed report and fix the issues.")
        return 1
    else:
        print("\n✅ No vulnerabilities detected in automated tests.")
        return 0


if __name__ == "__main__":
    exit(main())