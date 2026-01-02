# AI Pricing Agent - Testing Framework Documentation

## Overview

This document provides comprehensive guidance for the testing framework implemented for the AI Pricing Agent system. The framework covers all aspects of quality assurance including unit testing, integration testing, end-to-end testing, performance testing, security testing, ML model validation, and data quality testing.

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Test Categories](#test-categories)
5. [Coverage Requirements](#coverage-requirements)
6. [Test Data Management](#test-data-management)
7. [CI/CD Integration](#cicd-integration)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Performance Guidelines](#performance-guidelines)

## Testing Philosophy

Our testing framework follows the testing pyramid approach:

- **Unit Tests (70%)**: Fast, isolated tests for individual components
- **Integration Tests (20%)**: Tests for component interactions and API endpoints
- **End-to-End Tests (10%)**: Full user workflow tests using real browsers

### Quality Gates

- **Code Coverage**: Minimum 80% for all new code
- **Performance**: API responses < 200ms, ML predictions < 500ms
- **Security**: Zero high-severity vulnerabilities
- **Data Quality**: 100% validation rule compliance

## Test Structure

```
tests/
├── automation/           # Test automation and runners
├── data_quality/        # Data validation tests
├── fixtures/            # Test data fixtures
├── performance/         # Load and performance tests
└── security/           # Security and penetration tests

django_app/tests/
├── base.py             # Base test classes and mixins
├── conftest.py         # Django-specific fixtures
├── e2e/               # End-to-end browser tests
├── factories/         # Test data factories
├── fixtures/          # JSON test data
├── integration/       # API and service integration tests
└── unit/             # Unit tests by app
    ├── apps/
    │   ├── core/
    │   ├── pricing/
    │   ├── suppliers/
    │   └── analytics/
    └── utils/

fastapi_ml/tests/
├── conftest.py         # FastAPI-specific fixtures
├── fixtures/          # ML test data
├── integration/       # Service communication tests
├── ml/               # ML model validation tests
└── unit/             # FastAPI unit tests
    ├── api/
    ├── models/
    └── services/
```

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install -e ".[test]"

# Set up test environment
export DJANGO_SETTINGS_MODULE=pricing_agent.settings.test
export TESTING=true
```

### Basic Test Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=django_app --cov=fastapi_ml --cov-report=html

# Run specific test categories
pytest -m "unit"           # Unit tests only
pytest -m "integration"    # Integration tests only
pytest -m "slow"          # Slow tests (E2E, performance)

# Run tests for specific app
pytest django_app/tests/unit/apps/pricing/
pytest fastapi_ml/tests/unit/api/

# Run with parallel execution
pytest -n auto            # Auto-detect CPU cores
pytest -n 4              # Use 4 workers

# Run with verbose output
pytest -v --tb=short

# Run tests and stop on first failure
pytest -x
```

### Django-Specific Commands

```bash
# Run Django tests using manage.py
python django_app/manage.py test --settings=pricing_agent.settings.test

# Run with parallel execution
python django_app/manage.py test --parallel auto

# Generate coverage report
python django_app/manage.py test --with-coverage
```

### FastAPI-Specific Commands

```bash
# Run FastAPI tests only
pytest fastapi_ml/tests/

# Run async tests
pytest fastapi_ml/tests/ -v --asyncio-mode=auto
```

## Test Categories

### Unit Tests

Test individual components in isolation:

```bash
# Run all unit tests
pytest -m "unit"

# Test specific models
pytest django_app/tests/unit/apps/pricing/test_models.py

# Test specific API endpoints
pytest fastapi_ml/tests/unit/api/test_predictions.py
```

**Coverage Areas:**
- Django models, views, serializers, utilities
- FastAPI endpoints, services, ML models
- Business logic and calculations
- Input validation and error handling

### Integration Tests

Test component interactions and API endpoints:

```bash
# Run all integration tests
pytest -m "integration"

# Test API endpoints
pytest django_app/tests/integration/test_api_endpoints.py

# Test service communication
pytest fastapi_ml/tests/integration/test_service_communication.py
```

**Coverage Areas:**
- RESTful API endpoints
- Database interactions
- Redis caching layer
- Celery background tasks
- Service-to-service communication
- Multi-tenant data isolation

### End-to-End Tests

Test complete user workflows using Playwright:

```bash
# Install Playwright browsers
playwright install

# Run E2E tests
pytest -m "e2e"

# Run with browser UI (for debugging)
pytest -m "e2e" --headed

# Run on specific browser
pytest -m "e2e" --browser=chromium
pytest -m "e2e" --browser=firefox
pytest -m "e2e" --browser=webkit
```

**Coverage Areas:**
- User authentication and authorization
- RFQ creation and management workflows
- Supplier management interfaces
- Pricing analytics dashboards
- HTMX dynamic interactions
- Mobile responsiveness

### Performance Tests

Load and stress testing using Locust:

```bash
# Run performance tests
cd tests/performance
locust -f locustfile.py --host=http://localhost:8000

# Run headless performance test
locust -f locustfile.py --host=http://localhost:8000 --users 100 --spawn-rate 10 -t 60s --headless

# Run ML service performance tests
locust -f locustfile.py --host=http://localhost:8001 MLServiceUser --users 50 --spawn-rate 5 -t 30s --headless
```

**Performance Targets:**
- API Response Time: < 200ms (95th percentile)
- ML Predictions: < 500ms
- Database Queries: < 100ms
- Page Load Time: < 2 seconds
- Concurrent Users: 10,000+

### Security Tests

Automated security testing:

```bash
# Run basic security tests
pytest tests/security/security_tests.py

# Run penetration tests
pytest tests/security/penetration_tests.py

# Generate security report
pytest tests/security/ --security-report
```

**Security Coverage:**
- SQL injection protection
- XSS prevention
- Authentication bypass attempts
- Authorization checks
- Rate limiting validation
- Session security
- CSRF protection

### ML Model Tests

Validate ML model performance and detect drift:

```bash
# Run ML validation tests
pytest fastapi_ml/tests/ml/test_model_validation.py

# Run drift detection tests
pytest fastapi_ml/tests/ml/test_drift_detection.py

# Test with specific model
pytest fastapi_ml/tests/ml/ -k "test_pricing_model"
```

**ML Testing Areas:**
- Model accuracy and performance metrics
- Feature importance validation
- Edge case handling
- Data drift detection
- Concept drift monitoring
- Model fairness and bias testing

### Data Quality Tests

Validate data integrity and quality:

```bash
# Run data quality tests
pytest tests/data_quality/data_validation_tests.py

# Test specific data sources
pytest tests/data_quality/ -k "test_material_data"

# Generate data quality report
pytest tests/data_quality/ --data-quality-report
```

## Coverage Requirements

### Minimum Coverage Targets

- **Overall Code Coverage**: 80%
- **Critical Business Logic**: 95%
- **API Endpoints**: 90%
- **ML Models**: 85%
- **Security Functions**: 100%

### Generating Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=django_app --cov=fastapi_ml --cov-report=html
open htmlcov/index.html

# Generate terminal coverage report
pytest --cov=django_app --cov=fastapi_ml --cov-report=term-missing

# Generate XML coverage report (for CI)
pytest --cov=django_app --cov=fastapi_ml --cov-report=xml

# Check coverage with fail threshold
pytest --cov=django_app --cov=fastapi_ml --cov-fail-under=80
```

### Coverage Analysis

```bash
# Show uncovered lines
coverage report --show-missing

# Generate detailed coverage analysis
coverage html --include="django_app/*,fastapi_ml/*"

# Check coverage diff
coverage-diff-cover coverage.xml --compare-branch=main
```

## Test Data Management

### Using Factories

Test data is generated using factory_boy:

```python
from django_app.tests.factories import MaterialFactory, PriceFactory

# Create test data
material = MaterialFactory()
price = PriceFactory(material=material)

# Create batches
materials = MaterialFactory.create_batch(10)

# Override factory attributes
expensive_material = MaterialFactory(category__name="Premium Steel")
```

### Using Fixtures

Load predefined test data:

```python
import pytest
from django.core.management import call_command

@pytest.fixture
def sample_data(db):
    call_command('loaddata', 'sample_data.json')
```

### ML Test Data

Generate realistic ML test datasets:

```python
from fastapi_ml.tests.fixtures.ml_test_data import (
    generate_pricing_dataset,
    create_time_series_data,
    simulate_data_drift
)

# Generate synthetic pricing data
data = generate_pricing_dataset(n_samples=1000, add_noise=True)

# Create time series for testing
ts_data = create_time_series_data(
    start_date='2023-01-01',
    end_date='2024-01-01',
    frequency='daily'
)
```

## CI/CD Integration

### GitHub Actions Workflow

The CI/CD pipeline runs automatically on:
- Push to main/develop branches
- Pull requests
- Nightly scheduled runs

### Pipeline Stages

1. **Code Quality**
   - Linting (flake8, black, isort)
   - Type checking (mypy)
   - Security scanning (bandit)

2. **Unit Tests**
   - Django unit tests
   - FastAPI unit tests
   - Coverage reporting

3. **Integration Tests**
   - API endpoint testing
   - Database integration
   - Service communication

4. **Security Tests**
   - OWASP ZAP scanning
   - Dependency vulnerability check
   - Custom security tests

5. **End-to-End Tests**
   - Playwright browser tests
   - Multi-browser testing
   - Mobile responsiveness

6. **Performance Tests**
   - Load testing with Locust
   - Performance regression detection

### Local CI Simulation

```bash
# Run the same checks as CI
make ci-check

# Run individual CI stages
make lint
make test-unit
make test-integration
make test-e2e
make test-performance
make test-security
```

## Best Practices

### Writing Unit Tests

1. **Follow AAA Pattern**:
   ```python
   def test_material_price_calculation(self):
       # Arrange
       material = MaterialFactory(base_cost=100.0)
       
       # Act
       calculated_price = material.calculate_price(markup=0.2)
       
       # Assert
       assert calculated_price == 120.0
   ```

2. **Use Descriptive Test Names**:
   ```python
   def test_price_alert_triggers_when_threshold_exceeded(self):
   def test_material_deletion_cascades_to_related_prices(self):
   def test_unauthorized_user_cannot_access_supplier_data(self):
   ```

3. **Test Edge Cases**:
   ```python
   def test_price_calculation_with_zero_cost(self):
   def test_price_calculation_with_negative_markup(self):
   def test_price_calculation_with_extreme_values(self):
   ```

### Writing Integration Tests

1. **Test Real Interactions**:
   ```python
   @pytest.mark.integration
   def test_create_rfq_with_materials(self, client, auth_headers):
       materials = MaterialFactory.create_batch(3)
       rfq_data = {
           'title': 'Test RFQ',
           'materials': [{'id': m.id, 'quantity': 100} for m in materials]
       }
       response = client.post('/api/v1/rfqs/', json=rfq_data, headers=auth_headers)
       assert response.status_code == 201
   ```

2. **Verify Side Effects**:
   ```python
   def test_price_update_invalidates_cache(self, client):
       # Update price
       response = client.put('/api/v1/prices/1/', json={'amount': 150.0})
       
       # Verify cache invalidation
       cached_price = cache.get('price_1')
       assert cached_price is None
   ```

### Writing E2E Tests

1. **Test Complete User Journeys**:
   ```python
   @pytest.mark.e2e
   async def test_complete_rfq_workflow(self, page):
       # Login
       await page.goto('/login')
       await page.fill('#username', 'testuser')
       await page.fill('#password', 'testpass')
       await page.click('button[type=submit]')
       
       # Create RFQ
       await page.click('text=Create RFQ')
       await page.fill('#title', 'Test RFQ')
       await page.click('text=Add Material')
       
       # Verify creation
       await expect(page.locator('text=RFQ created successfully')).to_be_visible()
   ```

2. **Use Page Objects**:
   ```python
   class RFQPage:
       def __init__(self, page):
           self.page = page
           
       async def create_rfq(self, title, materials):
           await self.page.click('text=Create RFQ')
           await self.page.fill('#title', title)
           for material in materials:
               await self.add_material(material)
           await self.page.click('button[type=submit]')
   ```

### Performance Testing Guidelines

1. **Realistic Load Patterns**:
   ```python
   class WebUserBehavior(HttpUser):
       wait_time = between(1, 3)  # Realistic user think time
       
       @task(3)
       def browse_materials(self):
           self.client.get("/materials/")
           
       @task(1)
       def create_rfq(self):
           self.client.post("/rfqs/", json=self.get_rfq_data())
   ```

2. **Monitor Key Metrics**:
   - Response time percentiles (50th, 95th, 99th)
   - Error rates
   - Requests per second
   - Resource utilization

## Troubleshooting

### Common Test Failures

#### Database Errors

```bash
# Error: Database not found
# Solution: Ensure test database is configured
export DJANGO_SETTINGS_MODULE=pricing_agent.settings.test

# Error: Migration issues
# Solution: Run migrations for test database
python django_app/manage.py migrate --settings=pricing_agent.settings.test
```

#### Async Test Issues

```bash
# Error: RuntimeError: There is no current event loop
# Solution: Use pytest-asyncio plugin
pytest --asyncio-mode=auto

# Error: Task was destroyed but it is pending
# Solution: Properly clean up async resources in teardown
```

#### Memory Leaks in Tests

```bash
# Monitor memory usage
pytest --memray

# Profile memory usage
python -m pytest --profile-mem tests/

# Use memory-efficient test data
# Avoid creating large datasets in fixtures
```

#### Flaky Tests

```bash
# Run tests multiple times to identify flakiness
pytest --count=10 tests/test_flaky.py

# Add delays for timing-sensitive tests
import asyncio
await asyncio.sleep(0.1)

# Use proper waits in E2E tests
await page.wait_for_selector('text=Success')
```

### Debug Mode

```bash
# Run tests with pdb debugging
pytest --pdb

# Debug on failure
pytest --pdb-trace

# Verbose output with traceback
pytest -vv --tb=long

# Show all print statements
pytest -s
```

### Test Data Issues

```bash
# Clear test database
python django_app/manage.py flush --settings=pricing_agent.settings.test

# Reset migrations
python django_app/manage.py migrate --fake-initial --settings=pricing_agent.settings.test

# Reload fixtures
python django_app/manage.py loaddata sample_data.json --settings=pricing_agent.settings.test
```

## Performance Guidelines

### Test Execution Speed

- **Unit Tests**: < 1 second per test
- **Integration Tests**: < 5 seconds per test
- **E2E Tests**: < 30 seconds per test

### Optimization Strategies

1. **Use In-Memory Databases**:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.sqlite3',
           'NAME': ':memory:',
       }
   }
   ```

2. **Disable Migrations**:
   ```python
   class DisableMigrations:
       def __contains__(self, item):
           return True
       def __getitem__(self, item):
           return None

   MIGRATION_MODULES = DisableMigrations()
   ```

3. **Use Factories Over Fixtures**:
   ```python
   # Faster - creates only what's needed
   material = MaterialFactory()
   
   # Slower - loads entire fixture file
   call_command('loaddata', 'materials.json')
   ```

4. **Parallel Test Execution**:
   ```bash
   # Auto-detect CPU cores
   pytest -n auto
   
   # Specify number of workers
   pytest -n 4
   ```

### Monitoring Test Performance

```bash
# Profile test execution time
pytest --durations=10

# Show slowest tests
pytest --durations=0 | head -20

# Generate performance report
pytest --benchmark-save=results tests/performance/
```

## Conclusion

This testing framework provides comprehensive coverage for all aspects of the AI Pricing Agent system. By following the guidelines and best practices outlined in this document, you can ensure high code quality, reliability, and maintainability.

For questions or issues with the testing framework, please refer to the troubleshooting section or contact the development team.