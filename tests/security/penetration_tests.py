"""
Advanced penetration testing for the AI Pricing Agent system.
"""
import requests
import json
import time
import hashlib
import base64
import threading
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs
import jwt
import secrets
import string
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class PenTestResult:
    """Result of a penetration test."""
    test_name: str
    vulnerability_type: str
    severity: str  # critical, high, medium, low
    description: str
    evidence: str
    remediation: str
    status: str  # vulnerable, secure, error
    details: Dict[str, Any]


class PenetrationTestFramework:
    """Advanced penetration testing framework."""
    
    def __init__(self, target_url: str, ml_service_url: str):
        self.target_url = target_url.rstrip('/')
        self.ml_service_url = ml_service_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 10
        self.results = []
        self.authenticated_session = requests.Session()
        self.auth_token = None
        
        # Common user agents for testing
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'PenTestBot/1.0'
        ]
        
        # Initialize authentication
        self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with the target application."""
        try:
            auth_data = {
                "email": "test@example.com",
                "password": "testpass123"
            }
            
            response = self.session.post(
                f"{self.target_url}/auth/login/",
                json=auth_data
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                if self.auth_token:
                    self.authenticated_session.headers.update({
                        "Authorization": f"Bearer {self.auth_token}"
                    })
                    return True
        except Exception as e:
            print(f"Authentication failed: {e}")
        
        return False
    
    def test_authentication_bypass(self) -> PenTestResult:
        """Test for authentication bypass vulnerabilities."""
        test_name = "Authentication Bypass"
        
        bypass_techniques = [
            # JWT manipulation
            {
                "name": "JWT None Algorithm",
                "headers": {"Authorization": "Bearer " + self._create_none_jwt()},
                "endpoint": "/api/v1/admin/users/"
            },
            # SQL injection in login
            {
                "name": "SQL Injection Login Bypass",
                "data": {"email": "admin' OR '1'='1' --", "password": "anything"},
                "endpoint": "/auth/login/"
            },
            # Header manipulation
            {
                "name": "X-Forwarded-For Bypass",
                "headers": {"X-Forwarded-For": "127.0.0.1"},
                "endpoint": "/api/v1/admin/"
            },
            # Cookie manipulation
            {
                "name": "Session Cookie Manipulation",
                "cookies": {"session": "admin", "user_id": "1"},
                "endpoint": "/api/v1/admin/"
            }
        ]
        
        vulnerabilities_found = []
        
        for technique in bypass_techniques:
            try:
                if technique["name"] == "SQL Injection Login Bypass":
                    response = self.session.post(
                        f"{self.target_url}{technique['endpoint']}",
                        json=technique["data"]
                    )
                else:
                    headers = technique.get("headers", {})
                    cookies = technique.get("cookies", {})
                    
                    response = self.session.get(
                        f"{self.target_url}{technique['endpoint']}",
                        headers=headers,
                        cookies=cookies
                    )
                
                # Check if bypass was successful
                if response.status_code == 200 and "admin" in response.text.lower():
                    vulnerabilities_found.append({
                        "technique": technique["name"],
                        "response_code": response.status_code,
                        "evidence": response.text[:200]
                    })
            
            except Exception as e:
                continue
        
        if vulnerabilities_found:
            return PenTestResult(
                test_name=test_name,
                vulnerability_type="Authentication Bypass",
                severity="critical",
                description="Authentication bypass vulnerabilities detected",
                evidence=str(vulnerabilities_found),
                remediation="Implement proper authentication validation, input sanitization, and secure session management",
                status="vulnerable",
                details={"vulnerabilities": vulnerabilities_found}
            )
        
        return PenTestResult(
            test_name=test_name,
            vulnerability_type="Authentication",
            severity="info",
            description="No authentication bypass vulnerabilities detected",
            evidence="All authentication bypass attempts failed",
            remediation="Continue monitoring authentication mechanisms",
            status="secure",
            details={}
        )
    
    def test_privilege_escalation(self) -> PenTestResult:
        """Test for privilege escalation vulnerabilities."""
        test_name = "Privilege Escalation"
        
        # Test various privilege escalation techniques
        escalation_attempts = []
        
        # 1. Parameter manipulation
        try:
            # Try to access admin functions with modified parameters
            response = self.authenticated_session.post(
                f"{self.target_url}/api/v1/users/",
                json={
                    "username": "escalated_user",
                    "email": "escalated@test.com",
                    "is_admin": True,
                    "is_superuser": True,
                    "role": "admin"
                }
            )
            
            escalation_attempts.append({
                "method": "Parameter Manipulation",
                "status_code": response.status_code,
                "response": response.text[:200]
            })
        
        except Exception:
            pass
        
        # 2. HTTP Method Override
        try:
            headers = {"X-HTTP-Method-Override": "POST"}
            response = self.authenticated_session.get(
                f"{self.target_url}/api/v1/admin/users/",
                headers=headers
            )
            
            escalation_attempts.append({
                "method": "HTTP Method Override",
                "status_code": response.status_code,
                "response": response.text[:200]
            })
        
        except Exception:
            pass
        
        # 3. Direct ID manipulation
        try:
            # Try to access other users' data by manipulating IDs
            response = self.authenticated_session.get(
                f"{self.target_url}/api/v1/users/1/"  # Assuming user ID 1 is admin
            )
            
            if response.status_code == 200 and "admin" in response.text.lower():
                escalation_attempts.append({
                    "method": "Direct Object Reference",
                    "status_code": response.status_code,
                    "response": response.text[:200]
                })
        
        except Exception:
            pass
        
        # Check for successful escalation
        successful_escalations = [
            attempt for attempt in escalation_attempts 
            if attempt["status_code"] in [200, 201] and 
            ("admin" in attempt["response"].lower() or "created" in attempt["response"].lower())
        ]
        
        if successful_escalations:
            return PenTestResult(
                test_name=test_name,
                vulnerability_type="Privilege Escalation",
                severity="critical",
                description="Privilege escalation vulnerabilities detected",
                evidence=str(successful_escalations),
                remediation="Implement proper authorization checks, validate user permissions, and use principle of least privilege",
                status="vulnerable",
                details={"successful_escalations": successful_escalations}
            )
        
        return PenTestResult(
            test_name=test_name,
            vulnerability_type="Access Control",
            severity="info",
            description="No privilege escalation vulnerabilities detected",
            evidence="All escalation attempts properly blocked",
            remediation="Continue monitoring access controls",
            status="secure",
            details={}
        )
    
    def test_session_management(self) -> PenTestResult:
        """Test session management security."""
        test_name = "Session Management"
        
        session_issues = []
        
        # 1. Session Fixation
        try:
            # Get initial session
            response1 = self.session.get(f"{self.target_url}/")
            initial_session = response1.cookies.get('sessionid')
            
            if initial_session:
                # Try to login with fixed session
                response2 = self.session.post(
                    f"{self.target_url}/auth/login/",
                    json={"email": "test@example.com", "password": "testpass123"},
                    cookies={'sessionid': initial_session}
                )
                
                if response2.status_code == 200:
                    final_session = response2.cookies.get('sessionid')
                    if initial_session == final_session:
                        session_issues.append({
                            "issue": "Session Fixation",
                            "description": "Session ID not regenerated after login"
                        })
        
        except Exception:
            pass
        
        # 2. Session Timeout
        try:
            # Create a session and wait
            old_token = self.auth_token
            time.sleep(2)  # Short wait for testing
            
            # Try to use old token
            response = requests.get(
                f"{self.target_url}/api/v1/materials/",
                headers={"Authorization": f"Bearer {old_token}"}
            )
            
            # Check if old token is still valid (should be for short timeout)
            # In production, test with longer timeouts
            
        except Exception:
            pass
        
        # 3. Concurrent Session
        try:
            # Login from multiple locations
            session1 = requests.Session()
            session2 = requests.Session()
            
            auth_data = {"email": "test@example.com", "password": "testpass123"}
            
            resp1 = session1.post(f"{self.target_url}/auth/login/", json=auth_data)
            resp2 = session2.post(f"{self.target_url}/auth/login/", json=auth_data)
            
            if resp1.status_code == 200 and resp2.status_code == 200:
                # Both sessions should not be allowed simultaneously
                token1 = resp1.json().get("access_token")
                token2 = resp2.json().get("access_token")
                
                if token1 and token2 and token1 != token2:
                    # Test if both tokens work
                    test1 = session1.get(
                        f"{self.target_url}/api/v1/materials/",
                        headers={"Authorization": f"Bearer {token1}"}
                    )
                    test2 = session2.get(
                        f"{self.target_url}/api/v1/materials/",
                        headers={"Authorization": f"Bearer {token2}"}
                    )
                    
                    if test1.status_code == 200 and test2.status_code == 200:
                        session_issues.append({
                            "issue": "Concurrent Sessions Allowed",
                            "description": "Multiple simultaneous sessions allowed for same user"
                        })
        
        except Exception:
            pass
        
        if session_issues:
            return PenTestResult(
                test_name=test_name,
                vulnerability_type="Session Management",
                severity="medium",
                description="Session management issues detected",
                evidence=str(session_issues),
                remediation="Implement secure session management: regenerate session IDs, set proper timeouts, limit concurrent sessions",
                status="vulnerable",
                details={"session_issues": session_issues}
            )
        
        return PenTestResult(
            test_name=test_name,
            vulnerability_type="Session Management",
            severity="info",
            description="Session management appears secure",
            evidence="No obvious session management issues detected",
            remediation="Continue monitoring session security",
            status="secure",
            details={}
        )
    
    def test_business_logic_flaws(self) -> PenTestResult:
        """Test for business logic vulnerabilities."""
        test_name = "Business Logic Flaws"
        
        logic_flaws = []
        
        # 1. Price Manipulation
        try:
            # Try to submit RFQ with negative prices
            rfq_data = {
                "title": "Logic Test RFQ",
                "materials": [{
                    "description": "Test Material",
                    "quantity": -1000,  # Negative quantity
                    "target_price": -100  # Negative price
                }]
            }
            
            response = self.authenticated_session.post(
                f"{self.target_url}/api/v1/rfqs/",
                json=rfq_data
            )
            
            if response.status_code in [200, 201]:
                logic_flaws.append({
                    "flaw": "Negative Values Accepted",
                    "description": "System accepts negative quantities/prices",
                    "response_code": response.status_code
                })
        
        except Exception:
            pass
        
        # 2. Workflow Bypass
        try:
            # Try to skip approval workflow
            quote_data = {
                "rfq_id": 1,
                "status": "approved",  # Try to set approved status directly
                "total_price": 1000,
                "auto_approve": True
            }
            
            response = self.authenticated_session.post(
                f"{self.target_url}/api/v1/quotes/",
                json=quote_data
            )
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                if response_data.get("status") == "approved":
                    logic_flaws.append({
                        "flaw": "Workflow Bypass",
                        "description": "Approval workflow can be bypassed",
                        "response_code": response.status_code
                    })
        
        except Exception:
            pass
        
        # 3. Race Condition in Concurrent Operations
        try:
            def concurrent_operation():
                return self.authenticated_session.post(
                    f"{self.target_url}/api/v1/materials/",
                    json={"name": "Race Test Material", "code": "RACE001"}
                )
            
            # Perform concurrent requests
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(concurrent_operation) for _ in range(10)]
                results = [future.result() for future in as_completed(futures)]
            
            successful_creations = [r for r in results if r.status_code in [200, 201]]
            
            # If multiple materials with same code were created, it's a race condition
            if len(successful_creations) > 1:
                logic_flaws.append({
                    "flaw": "Race Condition",
                    "description": "Concurrent operations can create duplicate entries",
                    "successful_requests": len(successful_creations)
                })
        
        except Exception:
            pass
        
        # 4. ML Prediction Manipulation
        try:
            # Try to manipulate ML predictions
            prediction_data = {
                "material_specifications": {
                    "material_type": "steel",
                    "grade": "A36",
                    "thickness": 999999,  # Extreme value
                    "width": -100,  # Negative value
                    "length": 0  # Zero value
                },
                "quantity": 999999999,
                "force_prediction": True,
                "override_validation": True
            }
            
            response = self.session.post(
                f"{self.ml_service_url}/api/v1/predictions/",
                json=prediction_data
            )
            
            if response.status_code == 200:
                pred_data = response.json()
                prediction = pred_data.get("prediction", 0)
                
                # Check if prediction is unrealistic
                if prediction < 0 or prediction > 1000000:
                    logic_flaws.append({
                        "flaw": "ML Prediction Manipulation",
                        "description": "Unrealistic predictions accepted",
                        "prediction": prediction
                    })
        
        except Exception:
            pass
        
        if logic_flaws:
            return PenTestResult(
                test_name=test_name,
                vulnerability_type="Business Logic",
                severity="high",
                description="Business logic flaws detected",
                evidence=str(logic_flaws),
                remediation="Implement proper business rule validation, input constraints, and workflow controls",
                status="vulnerable",
                details={"logic_flaws": logic_flaws}
            )
        
        return PenTestResult(
            test_name=test_name,
            vulnerability_type="Business Logic",
            severity="info",
            description="No obvious business logic flaws detected",
            evidence="Business logic validation appears to be working",
            remediation="Continue monitoring business logic integrity",
            status="secure",
            details={}
        )
    
    def test_data_exposure(self) -> PenTestResult:
        """Test for sensitive data exposure."""
        test_name = "Data Exposure"
        
        data_exposures = []
        
        # 1. API Enumeration
        try:
            # Test various API endpoints for data leakage
            sensitive_endpoints = [
                "/api/v1/users/",
                "/api/v1/admin/",
                "/api/v1/debug/",
                "/api/v1/config/",
                "/.env",
                "/admin/",
                "/debug/",
                "/api/docs/",
                "/api/redoc/",
                "/swagger.json"
            ]
            
            for endpoint in sensitive_endpoints:
                try:
                    response = self.session.get(f"{self.target_url}{endpoint}")
                    
                    # Check for sensitive information in response
                    sensitive_patterns = [
                        "password", "secret", "key", "token", "api_key",
                        "database", "connection", "config", "env"
                    ]
                    
                    if response.status_code == 200:
                        response_text = response.text.lower()
                        exposed_data = [
                            pattern for pattern in sensitive_patterns 
                            if pattern in response_text
                        ]
                        
                        if exposed_data:
                            data_exposures.append({
                                "endpoint": endpoint,
                                "status_code": response.status_code,
                                "exposed_data": exposed_data,
                                "sample": response.text[:200]
                            })
                
                except Exception:
                    continue
        
        except Exception:
            pass
        
        # 2. Error Message Information Disclosure
        try:
            # Try to trigger verbose error messages
            error_triggers = [
                {"endpoint": "/api/v1/materials/99999999/", "method": "GET"},
                {"endpoint": "/api/v1/users/", "method": "POST", "data": {"invalid": "data"}},
                {"endpoint": "/api/v1/materials/", "method": "POST", "data": None},
            ]
            
            for trigger in error_triggers:
                try:
                    if trigger["method"] == "GET":
                        response = self.session.get(f"{self.target_url}{trigger['endpoint']}")
                    else:
                        response = self.session.post(
                            f"{self.target_url}{trigger['endpoint']}", 
                            json=trigger.get("data")
                        )
                    
                    # Check for detailed error messages
                    if response.status_code >= 400:
                        error_text = response.text.lower()
                        if any(word in error_text for word in ["traceback", "stack", "file", "line", "exception"]):
                            data_exposures.append({
                                "type": "Verbose Error Messages",
                                "endpoint": trigger["endpoint"],
                                "status_code": response.status_code,
                                "error_details": response.text[:300]
                            })
                
                except Exception:
                    continue
        
        except Exception:
            pass
        
        # 3. Directory Traversal for Sensitive Files
        try:
            sensitive_files = [
                "../../etc/passwd",
                "../../etc/shadow",
                "../../../windows/system32/config/sam",
                "../../app/.env",
                "../../app/settings.py"
            ]
            
            for file_path in sensitive_files:
                try:
                    response = self.session.get(
                        f"{self.target_url}/api/v1/files/{file_path}"
                    )
                    
                    if response.status_code == 200 and len(response.text) > 10:
                        data_exposures.append({
                            "type": "File Access",
                            "file_path": file_path,
                            "status_code": response.status_code,
                            "content_sample": response.text[:200]
                        })
                
                except Exception:
                    continue
        
        except Exception:
            pass
        
        if data_exposures:
            return PenTestResult(
                test_name=test_name,
                vulnerability_type="Data Exposure",
                severity="high",
                description="Sensitive data exposure detected",
                evidence=str(data_exposures),
                remediation="Remove debug endpoints, sanitize error messages, implement proper access controls for sensitive data",
                status="vulnerable",
                details={"data_exposures": data_exposures}
            )
        
        return PenTestResult(
            test_name=test_name,
            vulnerability_type="Data Protection",
            severity="info",
            description="No obvious data exposure detected",
            evidence="Sensitive data appears to be properly protected",
            remediation="Continue monitoring data access controls",
            status="secure",
            details={}
        )
    
    def test_ml_service_security(self) -> PenTestResult:
        """Test ML service specific security issues."""
        test_name = "ML Service Security"
        
        ml_vulnerabilities = []
        
        # 1. Model Poisoning Attempts
        try:
            # Try to poison training data
            poison_data = {
                "training_data": [
                    {
                        "features": {"material": "steel", "quantity": 1000},
                        "target": -999999  # Malicious target value
                    }
                ] * 100,  # Repeated malicious data
                "model_name": "poisoned_model",
                "force_retrain": True
            }
            
            response = self.session.post(
                f"{self.ml_service_url}/api/v1/training/",
                json=poison_data
            )
            
            if response.status_code in [200, 201, 202]:
                ml_vulnerabilities.append({
                    "vulnerability": "Training Data Manipulation",
                    "description": "ML service accepts potentially malicious training data",
                    "response_code": response.status_code
                })
        
        except Exception:
            pass
        
        # 2. Model Extraction
        try:
            # Try to extract model information
            extraction_attempts = [
                {"endpoint": "/api/v1/models/weights/"},
                {"endpoint": "/api/v1/models/architecture/"},
                {"endpoint": "/api/v1/models/export/"},
                {"endpoint": "/api/v1/debug/model/"}
            ]
            
            for attempt in extraction_attempts:
                try:
                    response = self.session.get(
                        f"{self.ml_service_url}{attempt['endpoint']}"
                    )
                    
                    if response.status_code == 200 and len(response.text) > 100:
                        ml_vulnerabilities.append({
                            "vulnerability": "Model Information Exposure",
                            "endpoint": attempt["endpoint"],
                            "description": "ML model details accessible without authentication",
                            "response_code": response.status_code
                        })
                
                except Exception:
                    continue
        
        except Exception:
            pass
        
        # 3. Adversarial Input Testing
        try:
            # Test with adversarial inputs
            adversarial_inputs = [
                {
                    "material_specifications": {
                        "material_type": "steel" + "X" * 1000,  # Extremely long input
                        "grade": "A36",
                        "thickness": float('inf'),  # Infinite value
                        "width": float('nan'),  # NaN value
                    },
                    "quantity": 10**15  # Extremely large number
                },
                {
                    "material_specifications": {
                        "material_type": "<script>alert('xss')</script>",
                        "grade": "'; DROP TABLE predictions; --",
                        "thickness": -999999,
                    },
                    "quantity": -1
                }
            ]
            
            for adv_input in adversarial_inputs:
                try:
                    response = self.session.post(
                        f"{self.ml_service_url}/api/v1/predictions/",
                        json=adv_input
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        prediction = result.get("prediction", 0)
                        
                        # Check for unrealistic or dangerous predictions
                        if prediction < 0 or prediction > 10**10 or str(prediction) == 'inf':
                            ml_vulnerabilities.append({
                                "vulnerability": "Adversarial Input Acceptance",
                                "description": "ML service produces unrealistic predictions for adversarial inputs",
                                "prediction": str(prediction),
                                "input": str(adv_input)[:200]
                            })
                
                except Exception:
                    continue
        
        except Exception:
            pass
        
        if ml_vulnerabilities:
            return PenTestResult(
                test_name=test_name,
                vulnerability_type="ML Security",
                severity="high",
                description="ML service security vulnerabilities detected",
                evidence=str(ml_vulnerabilities),
                remediation="Implement input validation, model access controls, secure training pipelines, and adversarial input detection",
                status="vulnerable",
                details={"ml_vulnerabilities": ml_vulnerabilities}
            )
        
        return PenTestResult(
            test_name=test_name,
            vulnerability_type="ML Security",
            severity="info",
            description="No obvious ML security vulnerabilities detected",
            evidence="ML service security controls appear adequate",
            remediation="Continue monitoring ML pipeline security",
            status="secure",
            details={}
        )
    
    def _create_none_jwt(self) -> str:
        """Create a JWT token with 'none' algorithm for testing."""
        header = {"alg": "none", "typ": "JWT"}
        payload = {"user_id": 1, "email": "admin@test.com", "is_admin": True}
        
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        
        return f"{header_b64}.{payload_b64}."
    
    def run_all_tests(self) -> List[PenTestResult]:
        """Run all penetration tests."""
        print("Starting comprehensive penetration testing...")
        
        tests = [
            self.test_authentication_bypass,
            self.test_privilege_escalation,
            self.test_session_management,
            self.test_business_logic_flaws,
            self.test_data_exposure,
            self.test_ml_service_security
        ]
        
        results = []
        for test in tests:
            try:
                result = test()
                results.append(result)
                print(f"Completed: {result.test_name} - Status: {result.status}")
            except Exception as e:
                error_result = PenTestResult(
                    test_name=test.__name__,
                    vulnerability_type="Test Error",
                    severity="info",
                    description=f"Test execution error: {str(e)}",
                    evidence="",
                    remediation="Check test configuration",
                    status="error",
                    details={"error": str(e)}
                )
                results.append(error_result)
        
        return results


def generate_penetration_test_report(results: List[PenTestResult], output_file: str = "pentest_report.json"):
    """Generate comprehensive penetration test report."""
    
    # Categorize results
    vulnerable_tests = [r for r in results if r.status == "vulnerable"]
    secure_tests = [r for r in results if r.status == "secure"]
    error_tests = [r for r in results if r.status == "error"]
    
    # Count by severity
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for result in vulnerable_tests:
        severity_counts[result.severity] += 1
    
    report = {
        "executive_summary": {
            "total_tests": len(results),
            "vulnerabilities_found": len(vulnerable_tests),
            "tests_passed": len(secure_tests),
            "test_errors": len(error_tests),
            "severity_breakdown": severity_counts,
            "overall_risk": _calculate_overall_risk(severity_counts)
        },
        "detailed_results": [
            {
                "test_name": r.test_name,
                "vulnerability_type": r.vulnerability_type,
                "severity": r.severity,
                "status": r.status,
                "description": r.description,
                "evidence": r.evidence,
                "remediation": r.remediation,
                "details": r.details
            }
            for r in results
        ],
        "recommendations": _generate_recommendations(vulnerable_tests)
    }
    
    # Save JSON report
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Generate human-readable summary
    summary_file = output_file.replace('.json', '_summary.txt')
    with open(summary_file, 'w') as f:
        f.write("PENETRATION TEST REPORT\n")
        f.write("=" * 50 + "\n\n")
        
        f.write("EXECUTIVE SUMMARY\n")
        f.write("-" * 20 + "\n")
        f.write(f"Total Tests Conducted: {len(results)}\n")
        f.write(f"Vulnerabilities Found: {len(vulnerable_tests)}\n")
        f.write(f"Tests Passed: {len(secure_tests)}\n")
        f.write(f"Test Errors: {len(error_tests)}\n")
        f.write(f"Overall Risk Level: {report['executive_summary']['overall_risk']}\n\n")
        
        if vulnerable_tests:
            f.write("CRITICAL VULNERABILITIES\n")
            f.write("-" * 25 + "\n")
            for vuln in vulnerable_tests:
                if vuln.severity == "critical":
                    f.write(f"• {vuln.test_name}: {vuln.description}\n")
                    f.write(f"  Remediation: {vuln.remediation}\n\n")
            
            f.write("HIGH SEVERITY VULNERABILITIES\n")
            f.write("-" * 30 + "\n")
            for vuln in vulnerable_tests:
                if vuln.severity == "high":
                    f.write(f"• {vuln.test_name}: {vuln.description}\n")
                    f.write(f"  Remediation: {vuln.remediation}\n\n")
        
        f.write("RECOMMENDATIONS\n")
        f.write("-" * 15 + "\n")
        for rec in report["recommendations"]:
            f.write(f"• {rec}\n")
    
    print(f"Penetration test report saved to: {output_file}")
    print(f"Summary report saved to: {summary_file}")


def _calculate_overall_risk(severity_counts: Dict[str, int]) -> str:
    """Calculate overall risk level based on vulnerability severity."""
    if severity_counts["critical"] > 0:
        return "CRITICAL"
    elif severity_counts["high"] > 2:
        return "HIGH"
    elif severity_counts["high"] > 0 or severity_counts["medium"] > 3:
        return "MEDIUM"
    elif severity_counts["medium"] > 0 or severity_counts["low"] > 0:
        return "LOW"
    else:
        return "MINIMAL"


def _generate_recommendations(vulnerable_tests: List[PenTestResult]) -> List[str]:
    """Generate security recommendations based on found vulnerabilities."""
    recommendations = []
    
    vulnerability_types = set(test.vulnerability_type for test in vulnerable_tests)
    
    if "Authentication Bypass" in vulnerability_types:
        recommendations.append("Implement multi-factor authentication and robust session management")
    
    if "Privilege Escalation" in vulnerability_types:
        recommendations.append("Review and strengthen authorization controls and access permissions")
    
    if "Business Logic" in vulnerability_types:
        recommendations.append("Implement comprehensive business rule validation and workflow controls")
    
    if "Data Exposure" in vulnerability_types:
        recommendations.append("Remove debug endpoints and implement data classification and protection")
    
    if "ML Security" in vulnerability_types:
        recommendations.append("Secure ML pipeline with input validation and model protection measures")
    
    recommendations.extend([
        "Conduct regular security assessments and penetration testing",
        "Implement security monitoring and incident response procedures",
        "Provide security training for development team",
        "Establish secure development lifecycle practices"
    ])
    
    return recommendations


def main():
    """Main function for running penetration tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run penetration tests")
    parser.add_argument("--target", default="http://localhost:8000", help="Target application URL")
    parser.add_argument("--ml-service", default="http://localhost:8001", help="ML service URL")
    parser.add_argument("--output", default="pentest_report.json", help="Output report file")
    
    args = parser.parse_args()
    
    # Run penetration tests
    framework = PenetrationTestFramework(args.target, args.ml_service)
    results = framework.run_all_tests()
    
    # Generate report
    generate_penetration_test_report(results, args.output)
    
    # Print summary
    vulnerable_count = len([r for r in results if r.status == "vulnerable"])
    critical_count = len([r for r in results if r.status == "vulnerable" and r.severity == "critical"])
    
    print(f"\nPenetration Test Summary:")
    print(f"Total vulnerabilities found: {vulnerable_count}")
    print(f"Critical vulnerabilities: {critical_count}")
    
    if critical_count > 0:
        print("❌ CRITICAL vulnerabilities detected! Immediate action required.")
        return 1
    elif vulnerable_count > 0:
        print("⚠️ Vulnerabilities detected. Review and remediate.")
        return 1
    else:
        print("✅ No vulnerabilities detected in penetration tests.")
        return 0


if __name__ == "__main__":
    exit(main())