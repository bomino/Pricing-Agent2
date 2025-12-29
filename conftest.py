"""
Root conftest.py for pytest configuration and global fixtures.
"""
import os
import pytest
import django
from django.conf import settings
from django.test.utils import get_runner
from django.core.management import execute_from_command_line

# Configure Django settings for pytest
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pricing_agent.settings.test')


def pytest_configure(config):
    """
    Configure Django for pytest.
    """
    if not settings.configured:
        settings.configure()
    django.setup()


@pytest.fixture(scope='session', autouse=True)
def django_db_setup():
    """
    Set up test database.
    """
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }


@pytest.fixture(scope='session')
def django_db_blocker():
    """
    Fixture to control database access during tests.
    """
    return lambda: None


@pytest.fixture
def api_client():
    """
    Create API client for testing.
    """
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_api_client(django_user_model):
    """
    Create authenticated API client.
    """
    from rest_framework.test import APIClient
    from rest_framework.authtoken.models import Token
    
    client = APIClient()
    user = django_user_model.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    token, created = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    client.user = user
    return client


@pytest.fixture
def admin_api_client(django_user_model):
    """
    Create admin API client.
    """
    from rest_framework.test import APIClient
    from rest_framework.authtoken.models import Token
    
    client = APIClient()
    admin_user = django_user_model.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )
    token, created = Token.objects.get_or_create(user=admin_user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    client.user = admin_user
    return client


@pytest.fixture
def mock_ml_service():
    """
    Mock ML service responses.
    """
    import responses
    
    with responses.RequestsMock() as rsps:
        # Mock prediction endpoint
        rsps.add(
            responses.POST,
            'http://testserver:8001/api/v1/predictions/',
            json={
                'prediction': 1250.50,
                'confidence': 0.85,
                'model_version': '1.0.0'
            },
            status=200
        )
        
        # Mock health check
        rsps.add(
            responses.GET,
            'http://testserver:8001/health',
            json={'status': 'healthy'},
            status=200
        )
        
        yield rsps


@pytest.fixture
def sample_rfq_data():
    """
    Sample RFQ data for testing.
    """
    return {
        'title': 'Test RFQ',
        'description': 'Test description',
        'category': 'Construction',
        'quantity': 100,
        'unit': 'pieces',
        'delivery_date': '2024-12-31',
        'specifications': {
            'material': 'Steel',
            'grade': 'A36',
            'dimensions': '10x10x1'
        }
    }


@pytest.fixture
def sample_supplier_data():
    """
    Sample supplier data for testing.
    """
    return {
        'name': 'Test Supplier Ltd',
        'email': 'supplier@test.com',
        'phone': '+1234567890',
        'address': '123 Test St, Test City, TC 12345',
        'categories': ['Construction', 'Materials'],
        'certifications': ['ISO9001', 'ISO14001']
    }


# Performance testing configuration
def pytest_addoption(parser):
    """
    Add pytest command line options.
    """
    parser.addoption(
        "--runslow", 
        action="store_true", 
        default=False, 
        help="run slow tests"
    )
    parser.addoption(
        "--performance", 
        action="store_true", 
        default=False, 
        help="run performance tests"
    )


def pytest_collection_modifyitems(config, items):
    """
    Skip slow tests unless --runslow is given.
    """
    if config.getoption("--runslow"):
        return
        
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    skip_performance = pytest.mark.skip(reason="need --performance option to run")
    
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
        if "performance" in item.keywords and not config.getoption("--performance"):
            item.add_marker(skip_performance)


# Test database settings
@pytest.fixture(scope='session')
def test_db():
    """
    Create test database.
    """
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'migrate', '--run-syncdb'])
    yield
    # Cleanup happens automatically with in-memory database