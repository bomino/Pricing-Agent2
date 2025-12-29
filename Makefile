# AI Pricing Agent - Testing Makefile
# Provides convenient commands for running different test suites

.PHONY: help install test test-unit test-integration test-e2e test-performance test-security test-ml test-data-quality coverage lint format ci-check clean

# Default target
help:
	@echo "AI Pricing Agent - Testing Commands"
	@echo ""
	@echo "Setup:"
	@echo "  install           Install all dependencies including test dependencies"
	@echo "  install-e2e       Install Playwright browsers for E2E testing"
	@echo ""
	@echo "Testing:"
	@echo "  test              Run all tests"
	@echo "  test-unit         Run unit tests only"
	@echo "  test-integration  Run integration tests only"
	@echo "  test-e2e          Run end-to-end tests"
	@echo "  test-performance  Run performance tests with Locust"
	@echo "  test-security     Run security tests"
	@echo "  test-ml           Run ML model validation tests"
	@echo "  test-data-quality Run data quality validation tests"
	@echo "  test-parallel     Run tests in parallel"
	@echo "  test-fast         Run fast tests only (exclude slow tests)"
	@echo ""
	@echo "Coverage:"
	@echo "  coverage          Generate coverage report"
	@echo "  coverage-html     Generate HTML coverage report"
	@echo "  coverage-xml      Generate XML coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint              Run linting checks"
	@echo "  format            Format code with black and isort"
	@echo "  type-check        Run mypy type checking"
	@echo "  security-scan     Run bandit security scanning"
	@echo ""
	@echo "CI/CD:"
	@echo "  ci-check          Run all CI checks locally"
	@echo "  pre-commit        Run pre-commit hooks"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean             Clean up test artifacts"
	@echo "  clean-coverage    Clean coverage reports"
	@echo "  clean-cache       Clean pytest cache"

# Setup targets
install:
	pip install -e ".[test]"
	pip install -r requirements-dev.txt

install-e2e:
	playwright install
	playwright install-deps

# Main testing targets
test:
	pytest --tb=short

test-unit:
	pytest -m "unit" --tb=short

test-integration:
	pytest -m "integration" --tb=short

test-e2e:
	pytest -m "e2e" --tb=short --browser=chromium

test-performance:
	cd tests/performance && locust -f locustfile.py --host=http://localhost:8000 --users 10 --spawn-rate 2 -t 30s --headless

test-security:
	pytest tests/security/ --tb=short

test-ml:
	pytest fastapi_ml/tests/ml/ --tb=short

test-data-quality:
	pytest tests/data_quality/ --tb=short

test-parallel:
	pytest -n auto --tb=short

test-fast:
	pytest -m "not slow" --tb=short

# Django-specific testing
test-django:
	cd django_app && python manage.py test --settings=pricing_agent.settings.test

test-django-parallel:
	cd django_app && python manage.py test --parallel auto --settings=pricing_agent.settings.test

# FastAPI-specific testing
test-fastapi:
	pytest fastapi_ml/tests/ --tb=short

test-fastapi-async:
	pytest fastapi_ml/tests/ --asyncio-mode=auto --tb=short

# Coverage targets
coverage:
	pytest --cov=django_app --cov=fastapi_ml --cov-report=term-missing

coverage-html:
	pytest --cov=django_app --cov=fastapi_ml --cov-report=html
	@echo "Coverage report generated: htmlcov/index.html"

coverage-xml:
	pytest --cov=django_app --cov=fastapi_ml --cov-report=xml

coverage-fail-under:
	pytest --cov=django_app --cov=fastapi_ml --cov-fail-under=80

# Code quality targets
lint:
	flake8 django_app/ fastapi_ml/ tests/
	black --check django_app/ fastapi_ml/ tests/
	isort --check-only django_app/ fastapi_ml/ tests/

format:
	black django_app/ fastapi_ml/ tests/
	isort django_app/ fastapi_ml/ tests/

type-check:
	mypy django_app/ fastapi_ml/

security-scan:
	bandit -r django_app/ fastapi_ml/ -f json -o bandit-report.json
	bandit -r django_app/ fastapi_ml/

# Specific test categories
test-models:
	pytest django_app/tests/unit/apps/*/test_models.py --tb=short

test-views:
	pytest django_app/tests/unit/apps/*/test_views.py --tb=short

test-serializers:
	pytest django_app/tests/unit/apps/*/test_serializers.py --tb=short

test-api-endpoints:
	pytest django_app/tests/integration/test_api_endpoints.py --tb=short

test-service-communication:
	pytest fastapi_ml/tests/integration/test_service_communication.py --tb=short

# Performance testing variants
test-load:
	cd tests/performance && locust -f locustfile.py --host=http://localhost:8000 --users 100 --spawn-rate 10 -t 60s --headless

test-stress:
	cd tests/performance && locust -f locustfile.py --host=http://localhost:8000 --users 1000 --spawn-rate 50 -t 120s --headless

test-ml-performance:
	cd tests/performance && locust -f locustfile.py --host=http://localhost:8001 MLServiceUser --users 50 --spawn-rate 5 -t 60s --headless

# Security testing variants
test-auth:
	pytest tests/security/security_tests.py::TestAuthentication --tb=short

test-authorization:
	pytest tests/security/security_tests.py::TestAuthorization --tb=short

test-injection:
	pytest tests/security/security_tests.py::TestInjectionAttacks --tb=short

test-penetration:
	pytest tests/security/penetration_tests.py --tb=short

# ML testing variants
test-model-validation:
	pytest fastapi_ml/tests/ml/test_model_validation.py --tb=short

test-drift-detection:
	pytest fastapi_ml/tests/ml/test_drift_detection.py --tb=short

test-feature-engineering:
	pytest fastapi_ml/tests/unit/services/test_feature_engineering.py --tb=short

# Database testing
test-migrations:
	cd django_app && python manage.py test --settings=pricing_agent.settings.test --tag=migration

test-database:
	pytest -k "database" --tb=short

test-transactions:
	pytest django_app/tests/unit/test_transactions.py --tb=short

# Cache testing
test-cache:
	pytest -k "cache" --tb=short

test-redis:
	pytest -k "redis" --tb=short

# Background task testing
test-celery:
	pytest -k "celery" --tb=short

test-tasks:
	pytest -k "task" --tb=short

# Multi-tenant testing
test-tenants:
	pytest -k "tenant" --tb=short

test-isolation:
	pytest -k "isolation" --tb=short

# Browser-specific E2E testing
test-e2e-chromium:
	pytest -m "e2e" --browser=chromium --tb=short

test-e2e-firefox:
	pytest -m "e2e" --browser=firefox --tb=short

test-e2e-webkit:
	pytest -m "e2e" --browser=webkit --tb=short

test-e2e-mobile:
	pytest -m "e2e" --device="iPhone 12" --tb=short

# Debug testing
test-debug:
	pytest -vv --tb=long --pdb

test-debug-last-failed:
	pytest --lf -vv --tb=long --pdb

test-verbose:
	pytest -vv --tb=long

# Test data management
fixtures-load:
	cd django_app && python manage.py loaddata tests/fixtures/sample_data.json --settings=pricing_agent.settings.test

fixtures-dump:
	cd django_app && python manage.py dumpdata --settings=pricing_agent.settings.test --indent=2 > tests/fixtures/sample_data.json

test-data-clean:
	cd django_app && python manage.py flush --noinput --settings=pricing_agent.settings.test

# CI/CD targets
ci-check: lint type-check security-scan test coverage-fail-under

ci-unit:
	pytest -m "unit" --cov=django_app --cov=fastapi_ml --cov-report=xml --junitxml=junit.xml

ci-integration:
	pytest -m "integration" --junitxml=junit-integration.xml

ci-e2e:
	pytest -m "e2e" --browser=chromium --junitxml=junit-e2e.xml

ci-security:
	pytest tests/security/ --junitxml=junit-security.xml

pre-commit:
	pre-commit run --all-files

# Cleanup targets
clean: clean-coverage clean-cache clean-reports

clean-coverage:
	rm -rf htmlcov/
	rm -f coverage.xml
	rm -f .coverage
	rm -f .coverage.*

clean-cache:
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

clean-reports:
	rm -f junit*.xml
	rm -f bandit-report.json
	rm -f test-results.xml

clean-e2e:
	rm -rf test-results/
	rm -rf playwright-report/

# Development helpers
watch-tests:
	pytest-watch -- --tb=short

test-changed:
	pytest --testmon --tb=short

test-new:
	pytest --testmon-noselect --tb=short

# Documentation
test-docs:
	cd docs && make test

docs-coverage:
	interrogate django_app/ fastapi_ml/ --ignore-init-method --ignore-magic

# Environment setup
setup-test-db:
	cd django_app && python manage.py migrate --settings=pricing_agent.settings.test
	cd django_app && python manage.py loaddata tests/fixtures/sample_data.json --settings=pricing_agent.settings.test

setup-dev:
	pip install -e ".[dev]"
	pre-commit install
	make setup-test-db
	make install-e2e

# Test automation
test-automation:
	python tests/automation/test_runner.py --suite=all

test-automation-parallel:
	python tests/automation/test_runner.py --suite=all --parallel=true

test-automation-report:
	python tests/automation/test_runner.py --suite=all --report=true

# Container testing
test-docker:
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

test-docker-clean:
	docker-compose -f docker-compose.test.yml down -v

# Test monitoring
test-monitor:
	pytest --live-log --log-cli-level=INFO

test-profile:
	pytest --profile

test-benchmark:
	pytest --benchmark-only

# Conditional targets based on environment
ifeq ($(CI),true)
test: ci-unit
coverage: coverage-xml
endif

# Help for specific categories
help-testing:
	@echo "Testing Commands:"
	@echo "  test              - Run all tests"
	@echo "  test-unit         - Run unit tests only"
	@echo "  test-integration  - Run integration tests"
	@echo "  test-e2e          - Run end-to-end tests"
	@echo "  test-performance  - Run performance tests"
	@echo "  test-security     - Run security tests"

help-coverage:
	@echo "Coverage Commands:"
	@echo "  coverage          - Generate terminal coverage report"
	@echo "  coverage-html     - Generate HTML coverage report"
	@echo "  coverage-xml      - Generate XML coverage report (for CI)"
	@echo "  coverage-fail-under - Fail if coverage below 80%"