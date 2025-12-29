"""
Automated test runner for the AI Pricing Agent testing framework.
"""
import os
import sys
import subprocess
import argparse
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
import concurrent.futures
from enum import Enum


class TestType(Enum):
    """Types of tests that can be executed."""
    UNIT = "unit"
    INTEGRATION = "integration" 
    E2E = "e2e"
    PERFORMANCE = "performance"
    SECURITY = "security"
    ML_MODEL = "ml_model"
    DATA_QUALITY = "data_quality"
    ALL = "all"


@dataclass
class TestResult:
    """Result of a test execution."""
    test_type: str
    status: str  # 'pass', 'fail', 'error', 'skipped'
    duration: float
    output: str
    error_output: str
    coverage: Optional[float] = None
    test_count: Optional[int] = None
    failed_count: Optional[int] = None
    details: Dict[str, Any] = None


class TestRunner:
    """Automated test execution framework."""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.results = []
        self.start_time = None
        self.end_time = None
        
        # Configuration
        self.python_executable = sys.executable
        self.coverage_threshold = {
            'django': 80,
            'fastapi': 75,
            'overall': 80
        }
        
        # Paths
        self.django_app_path = self.project_root / "django_app"
        self.fastapi_path = self.project_root / "fastapi_ml"
        self.tests_path = self.project_root / "tests"
    
    def run_test_suite(self, test_types: List[TestType], 
                      parallel: bool = False,
                      fail_fast: bool = False,
                      verbose: bool = True) -> Dict[str, Any]:
        """Run the specified test suite."""
        print(f"🚀 Starting test execution at {datetime.now().isoformat()}")
        print(f"📍 Project root: {self.project_root}")
        print(f"🔬 Test types: {[t.value for t in test_types]}")
        
        self.start_time = time.time()
        
        if TestType.ALL in test_types:
            test_types = [t for t in TestType if t != TestType.ALL]
        
        try:
            if parallel and len(test_types) > 1:
                self._run_tests_parallel(test_types, verbose)
            else:
                self._run_tests_sequential(test_types, fail_fast, verbose)
        
        except KeyboardInterrupt:
            print("⚠️ Test execution interrupted by user")
            return self._generate_summary(interrupted=True)
        
        except Exception as e:
            print(f"❌ Test execution failed with error: {e}")
            return self._generate_summary(error=str(e))
        
        finally:
            self.end_time = time.time()
        
        return self._generate_summary()
    
    def _run_tests_sequential(self, test_types: List[TestType], 
                            fail_fast: bool, verbose: bool):
        """Run tests sequentially."""
        for test_type in test_types:
            print(f"\n{'='*60}")
            print(f"🧪 Running {test_type.value} tests")
            print(f"{'='*60}")
            
            result = self._execute_test_type(test_type, verbose)
            self.results.append(result)
            
            if fail_fast and result.status == 'fail':
                print(f"❌ Fast-failing on {test_type.value} test failure")
                break
    
    def _run_tests_parallel(self, test_types: List[TestType], verbose: bool):
        """Run tests in parallel."""
        print("🔄 Running tests in parallel...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_test = {
                executor.submit(self._execute_test_type, test_type, verbose): test_type 
                for test_type in test_types
            }
            
            for future in concurrent.futures.as_completed(future_to_test):
                test_type = future_to_test[future]
                try:
                    result = future.result()
                    self.results.append(result)
                    status_icon = "✅" if result.status == 'pass' else "❌"
                    print(f"{status_icon} {test_type.value} tests completed")
                except Exception as e:
                    error_result = TestResult(
                        test_type=test_type.value,
                        status='error',
                        duration=0,
                        output='',
                        error_output=str(e)
                    )
                    self.results.append(error_result)
                    print(f"❌ {test_type.value} tests failed with error: {e}")
    
    def _execute_test_type(self, test_type: TestType, verbose: bool) -> TestResult:
        """Execute a specific type of test."""
        start_time = time.time()
        
        try:
            if test_type == TestType.UNIT:
                return self._run_unit_tests(start_time, verbose)
            elif test_type == TestType.INTEGRATION:
                return self._run_integration_tests(start_time, verbose)
            elif test_type == TestType.E2E:
                return self._run_e2e_tests(start_time, verbose)
            elif test_type == TestType.PERFORMANCE:
                return self._run_performance_tests(start_time, verbose)
            elif test_type == TestType.SECURITY:
                return self._run_security_tests(start_time, verbose)
            elif test_type == TestType.ML_MODEL:
                return self._run_ml_model_tests(start_time, verbose)
            elif test_type == TestType.DATA_QUALITY:
                return self._run_data_quality_tests(start_time, verbose)
            else:
                raise ValueError(f"Unknown test type: {test_type}")
        
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_type=test_type.value,
                status='error',
                duration=duration,
                output='',
                error_output=str(e)
            )
    
    def _run_unit_tests(self, start_time: float, verbose: bool) -> TestResult:
        """Run unit tests for both Django and FastAPI."""
        print("🔬 Running Django unit tests...")
        
        # Django unit tests
        django_cmd = [
            self.python_executable, "-m", "pytest",
            str(self.django_app_path / "tests" / "unit"),
            "-v" if verbose else "-q",
            "--cov=apps",
            "--cov-report=xml",
            "--cov-report=term-missing",
            f"--cov-fail-under={self.coverage_threshold['django']}",
            "--tb=short"
        ]
        
        django_result = self._run_command(django_cmd, cwd=self.django_app_path)
        
        print("🔬 Running FastAPI unit tests...")
        
        # FastAPI unit tests  
        fastapi_cmd = [
            self.python_executable, "-m", "pytest",
            str(self.fastapi_path / "tests" / "unit"),
            "-v" if verbose else "-q",
            "--cov=.",
            "--cov-report=xml",
            "--cov-report=term-missing",
            f"--cov-fail-under={self.coverage_threshold['fastapi']}",
            "--tb=short"
        ]
        
        fastapi_result = self._run_command(fastapi_cmd, cwd=self.fastapi_path)
        
        # Combine results
        combined_output = f"Django Tests:\n{django_result['stdout']}\n\nFastAPI Tests:\n{fastapi_result['stdout']}"
        combined_errors = f"Django Errors:\n{django_result['stderr']}\n\nFastAPI Errors:\n{fastapi_result['stderr']}"
        
        overall_success = django_result['returncode'] == 0 and fastapi_result['returncode'] == 0
        
        return TestResult(
            test_type="unit",
            status='pass' if overall_success else 'fail',
            duration=time.time() - start_time,
            output=combined_output,
            error_output=combined_errors,
            details={
                'django_result': django_result,
                'fastapi_result': fastapi_result
            }
        )
    
    def _run_integration_tests(self, start_time: float, verbose: bool) -> TestResult:
        """Run integration tests."""
        print("🔗 Running integration tests...")
        
        # Start services if needed
        self._ensure_test_services_running()
        
        cmd = [
            self.python_executable, "-m", "pytest",
            str(self.django_app_path / "tests" / "integration"),
            str(self.fastapi_path / "tests" / "integration"),
            "-v" if verbose else "-q",
            "--tb=short",
            "--maxfail=5"
        ]
        
        result = self._run_command(cmd)
        
        return TestResult(
            test_type="integration",
            status='pass' if result['returncode'] == 0 else 'fail',
            duration=time.time() - start_time,
            output=result['stdout'],
            error_output=result['stderr']
        )
    
    def _run_e2e_tests(self, start_time: float, verbose: bool) -> TestResult:
        """Run end-to-end tests."""
        print("🎭 Running end-to-end tests...")
        
        # Ensure services are running
        self._ensure_test_services_running()
        
        cmd = [
            self.python_executable, "-m", "pytest",
            str(self.django_app_path / "tests" / "e2e"),
            "-v" if verbose else "-q",
            "--tb=short",
            "-m", "not slow"  # Skip slow E2E tests in regular runs
        ]
        
        result = self._run_command(cmd)
        
        return TestResult(
            test_type="e2e",
            status='pass' if result['returncode'] == 0 else 'fail',
            duration=time.time() - start_time,
            output=result['stdout'],
            error_output=result['stderr']
        )
    
    def _run_performance_tests(self, start_time: float, verbose: bool) -> TestResult:
        """Run performance tests."""
        print("⚡ Running performance tests...")
        
        cmd = [
            self.python_executable,
            str(self.tests_path / "performance" / "performance_test_config.py"),
            "--scenario", "smoke"
        ]
        
        result = self._run_command(cmd)
        
        return TestResult(
            test_type="performance",
            status='pass' if result['returncode'] == 0 else 'fail',
            duration=time.time() - start_time,
            output=result['stdout'],
            error_output=result['stderr']
        )
    
    def _run_security_tests(self, start_time: float, verbose: bool) -> TestResult:
        """Run security tests."""
        print("🔒 Running security tests...")
        
        # Ensure services are running
        self._ensure_test_services_running()
        
        cmd = [
            self.python_executable,
            str(self.tests_path / "security" / "security_tests.py"),
            "--base-url", "http://localhost:8000",
            "--ml-url", "http://localhost:8001"
        ]
        
        result = self._run_command(cmd)
        
        return TestResult(
            test_type="security",
            status='pass' if result['returncode'] == 0 else 'fail',
            duration=time.time() - start_time,
            output=result['stdout'],
            error_output=result['stderr']
        )
    
    def _run_ml_model_tests(self, start_time: float, verbose: bool) -> TestResult:
        """Run ML model tests."""
        print("🤖 Running ML model tests...")
        
        cmd = [
            self.python_executable, "-m", "pytest",
            str(self.fastapi_path / "tests" / "ml"),
            "-v" if verbose else "-q",
            "--tb=short",
            "-m", "not slow"
        ]
        
        result = self._run_command(cmd, cwd=self.fastapi_path)
        
        return TestResult(
            test_type="ml_model",
            status='pass' if result['returncode'] == 0 else 'fail',
            duration=time.time() - start_time,
            output=result['stdout'],
            error_output=result['stderr']
        )
    
    def _run_data_quality_tests(self, start_time: float, verbose: bool) -> TestResult:
        """Run data quality tests."""
        print("📊 Running data quality tests...")
        
        cmd = [
            self.python_executable, "-m", "pytest",
            str(self.tests_path / "data_quality"),
            "-v" if verbose else "-q",
            "--tb=short"
        ]
        
        result = self._run_command(cmd)
        
        return TestResult(
            test_type="data_quality",
            status='pass' if result['returncode'] == 0 else 'fail',
            duration=time.time() - start_time,
            output=result['stdout'],
            error_output=result['stderr']
        )
    
    def _run_command(self, cmd: List[str], cwd: Path = None) -> Dict[str, Any]:
        """Run a shell command and return the result."""
        try:
            process = subprocess.run(
                cmd,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutes timeout
            )
            
            return {
                'returncode': process.returncode,
                'stdout': process.stdout,
                'stderr': process.stderr,
                'cmd': ' '.join(cmd)
            }
        
        except subprocess.TimeoutExpired:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': 'Command timed out after 30 minutes',
                'cmd': ' '.join(cmd)
            }
        
        except Exception as e:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'cmd': ' '.join(cmd)
            }
    
    def _ensure_test_services_running(self):
        """Ensure test services are running for integration/E2E tests."""
        # This is a placeholder - in practice, you would:
        # 1. Check if services are already running
        # 2. Start them if needed (using docker-compose, systemd, etc.)
        # 3. Wait for them to be ready
        print("📋 Checking test services...")
        
        # Example service checks
        services = [
            {'name': 'PostgreSQL', 'port': 5432},
            {'name': 'Redis', 'port': 6379},
            {'name': 'Django', 'port': 8000, 'path': '/health/'},
            {'name': 'FastAPI', 'port': 8001, 'path': '/health'}
        ]
        
        for service in services:
            print(f"  Checking {service['name']}...")
            # In real implementation, check if service is responding
    
    def _generate_summary(self, interrupted: bool = False, error: str = None) -> Dict[str, Any]:
        """Generate test execution summary."""
        total_duration = (self.end_time - self.start_time) if self.end_time and self.start_time else 0
        
        # Count results by status
        status_counts = {
            'pass': len([r for r in self.results if r.status == 'pass']),
            'fail': len([r for r in self.results if r.status == 'fail']),
            'error': len([r for r in self.results if r.status == 'error']),
            'skipped': len([r for r in self.results if r.status == 'skipped'])
        }
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_duration': round(total_duration, 2),
            'total_tests': len(self.results),
            'status_counts': status_counts,
            'pass_rate': status_counts['pass'] / len(self.results) if self.results else 0,
            'interrupted': interrupted,
            'error': error,
            'results': [asdict(result) for result in self.results]
        }
        
        # Determine overall status
        if error or interrupted:
            summary['overall_status'] = 'error'
        elif status_counts['fail'] > 0 or status_counts['error'] > 0:
            summary['overall_status'] = 'fail'
        else:
            summary['overall_status'] = 'pass'
        
        return summary
    
    def save_results(self, output_file: str = None):
        """Save test results to file."""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"test_results_{timestamp}.json"
        
        summary = self._generate_summary()
        
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📁 Test results saved to: {output_file}")
        
        return output_file
    
    def print_summary(self):
        """Print test execution summary."""
        summary = self._generate_summary()
        
        print(f"\n{'='*60}")
        print("📊 TEST EXECUTION SUMMARY")
        print(f"{'='*60}")
        
        print(f"⏱️  Total Duration: {summary['total_duration']:.2f} seconds")
        print(f"📈 Total Tests: {summary['total_tests']}")
        print(f"✅ Passed: {summary['status_counts']['pass']}")
        print(f"❌ Failed: {summary['status_counts']['fail']}")
        print(f"⚠️  Errors: {summary['status_counts']['error']}")
        print(f"⏭️  Skipped: {summary['status_counts']['skipped']}")
        print(f"📊 Pass Rate: {summary['pass_rate']:.1%}")
        
        status_icon = "✅" if summary['overall_status'] == 'pass' else "❌"
        print(f"\n{status_icon} Overall Status: {summary['overall_status'].upper()}")
        
        if summary['status_counts']['fail'] > 0 or summary['status_counts']['error'] > 0:
            print(f"\n{'='*60}")
            print("❌ FAILED TESTS:")
            print(f"{'='*60}")
            
            for result in self.results:
                if result.status in ['fail', 'error']:
                    print(f"• {result.test_type}: {result.status}")
                    if result.error_output:
                        # Print first few lines of error
                        error_lines = result.error_output.split('\n')[:3]
                        for line in error_lines:
                            if line.strip():
                                print(f"  {line}")
                    print()


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Automated test runner for AI Pricing Agent")
    
    parser.add_argument(
        'test_types',
        nargs='*',
        default=['all'],
        choices=[t.value for t in TestType],
        help='Types of tests to run'
    )
    
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run tests in parallel where possible'
    )
    
    parser.add_argument(
        '--fail-fast',
        action='store_true',
        help='Stop on first test failure'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimal output'
    )
    
    parser.add_argument(
        '--output',
        help='Output file for test results'
    )
    
    parser.add_argument(
        '--project-root',
        help='Project root directory'
    )
    
    args = parser.parse_args()
    
    # Parse test types
    test_types = []
    for test_type_str in args.test_types:
        try:
            test_types.append(TestType(test_type_str))
        except ValueError:
            print(f"❌ Invalid test type: {test_type_str}")
            sys.exit(1)
    
    # Create test runner
    runner = TestRunner(args.project_root)
    
    # Run tests
    summary = runner.run_test_suite(
        test_types=test_types,
        parallel=args.parallel,
        fail_fast=args.fail_fast,
        verbose=not args.quiet
    )
    
    # Print summary
    runner.print_summary()
    
    # Save results
    if args.output:
        runner.save_results(args.output)
    
    # Exit with appropriate code
    exit_code = 0 if summary['overall_status'] == 'pass' else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()