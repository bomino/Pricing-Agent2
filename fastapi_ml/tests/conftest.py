"""
FastAPI ML service test configuration and fixtures.
"""
import pytest
import asyncio
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from config import Settings
from dependencies import get_settings, get_redis_client
from models.schemas import PredictionRequest, ModelTrainingRequest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """Test settings configuration."""
    return Settings(
        database_url="sqlite:///test.db",
        redis_url="redis://localhost:6379/1",
        ml_model_path="test_models/",
        jwt_secret="test_secret",
        environment="test",
        debug=True
    )


@pytest.fixture
def override_settings(test_settings):
    """Override app settings for testing."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield test_settings
    app.dependency_overrides.clear()


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = Mock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = True
    redis_mock.exists.return_value = False
    return redis_mock


@pytest.fixture
def override_redis(mock_redis):
    """Override Redis dependency."""
    app.dependency_overrides[get_redis_client] = lambda: mock_redis
    yield mock_redis
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_settings, override_redis):
    """Test client for FastAPI app."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_client(override_settings, override_redis):
    """Async test client for FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    """Authentication headers for testing."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def sample_prediction_request():
    """Sample prediction request data."""
    return {
        "material_specifications": {
            "material_type": "steel",
            "grade": "A36",
            "thickness": 10.0,
            "width": 100.0,
            "length": 200.0
        },
        "quantity": 1000,
        "delivery_location": "New York, NY",
        "delivery_date": "2024-12-31",
        "features": {
            "supplier_category": "tier_1",
            "payment_terms": "net_30",
            "quality_requirements": ["ISO9001"]
        }
    }


@pytest.fixture
def sample_training_request():
    """Sample model training request data."""
    return {
        "model_name": "pricing_model_v2",
        "model_type": "lightgbm",
        "features": [
            "material_type", "grade", "thickness", "width", "length",
            "quantity", "delivery_distance", "supplier_tier"
        ],
        "target": "price_per_unit",
        "hyperparameters": {
            "n_estimators": 100,
            "learning_rate": 0.1,
            "max_depth": 6
        },
        "validation_split": 0.2
    }


@pytest.fixture
def sample_material_data():
    """Sample material data for testing."""
    return pd.DataFrame({
        'material_id': [1, 2, 3, 4, 5],
        'material_type': ['steel', 'aluminum', 'steel', 'plastic', 'steel'],
        'grade': ['A36', '6061', 'A572', 'ABS', 'A36'],
        'thickness': [10.0, 5.0, 15.0, 3.0, 12.0],
        'width': [100.0, 150.0, 200.0, 50.0, 120.0],
        'length': [200.0, 300.0, 400.0, 100.0, 250.0],
        'quantity': [1000, 500, 2000, 300, 1500],
        'delivery_distance': [100, 250, 150, 50, 200],
        'supplier_tier': [1, 2, 1, 3, 2],
        'price_per_unit': [10.50, 15.75, 12.25, 5.30, 11.20]
    })


@pytest.fixture
def sample_price_history():
    """Sample price history data for testing."""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    return pd.DataFrame({
        'date': dates,
        'material_id': np.random.choice([1, 2, 3], size=100),
        'price': np.random.normal(10.0, 2.0, 100),
        'quantity': np.random.randint(100, 2000, 100),
        'supplier_id': np.random.choice([1, 2, 3, 4, 5], size=100)
    })


@pytest.fixture
def mock_ml_model():
    """Mock ML model for testing."""
    model_mock = Mock()
    model_mock.predict.return_value = np.array([10.50])
    model_mock.predict_proba.return_value = np.array([[0.1, 0.9]])
    model_mock.feature_importances_ = np.array([0.3, 0.2, 0.15, 0.1, 0.25])
    return model_mock


@pytest.fixture
def mock_model_registry():
    """Mock model registry for testing."""
    with patch('services.model_registry.ModelRegistry') as mock_registry:
        registry_instance = mock_registry.return_value
        registry_instance.get_model.return_value = Mock()
        registry_instance.register_model.return_value = True
        registry_instance.list_models.return_value = [
            {"name": "test_model_v1", "version": "1.0", "status": "active"}
        ]
        yield registry_instance


@pytest.fixture
def mock_feature_engineering():
    """Mock feature engineering service."""
    with patch('services.feature_engineering.FeatureEngineering') as mock_fe:
        fe_instance = mock_fe.return_value
        fe_instance.extract_features.return_value = {
            'material_type_encoded': 1,
            'grade_encoded': 2,
            'volume': 20000.0,
            'density_score': 0.75
        }
        fe_instance.preprocess_data.return_value = pd.DataFrame({
            'feature1': [1, 2, 3],
            'feature2': [0.5, 0.7, 0.9]
        })
        yield fe_instance


@pytest.fixture
def mock_ml_service():
    """Mock ML service for testing."""
    with patch('services.ml_service.MLService') as mock_service:
        service_instance = mock_service.return_value
        service_instance.predict.return_value = {
            'prediction': 10.50,
            'confidence': 0.85,
            'model_version': 'v1.0.0',
            'features_used': ['material_type', 'quantity', 'grade']
        }
        service_instance.batch_predict.return_value = [
            {'prediction': 10.50, 'confidence': 0.85},
            {'prediction': 12.75, 'confidence': 0.92}
        ]
        yield service_instance


@pytest.fixture
def mock_training_pipeline():
    """Mock training pipeline for testing."""
    with patch('services.training_pipeline.TrainingPipeline') as mock_pipeline:
        pipeline_instance = mock_pipeline.return_value
        pipeline_instance.train_model.return_value = {
            'model_id': 'test_model_123',
            'training_score': 0.85,
            'validation_score': 0.82,
            'feature_importance': {
                'material_type': 0.3,
                'quantity': 0.25,
                'grade': 0.2
            }
        }
        pipeline_instance.evaluate_model.return_value = {
            'accuracy': 0.85,
            'precision': 0.83,
            'recall': 0.87,
            'f1_score': 0.85
        }
        yield pipeline_instance


@pytest.fixture
def mock_data_pipeline():
    """Mock data pipeline for testing."""
    with patch('services.data_pipeline.DataPipeline') as mock_pipeline:
        pipeline_instance = mock_pipeline.return_value
        pipeline_instance.load_data.return_value = pd.DataFrame({
            'material_id': [1, 2, 3],
            'price': [10.0, 15.0, 12.0]
        })
        pipeline_instance.validate_data.return_value = True
        pipeline_instance.process_data.return_value = pd.DataFrame({
            'feature1': [1, 2, 3],
            'feature2': [0.5, 0.7, 0.9],
            'target': [10.0, 15.0, 12.0]
        })
        yield pipeline_instance


@pytest.fixture
def mock_monitoring_service():
    """Mock monitoring service for testing."""
    with patch('services.monitoring.MonitoringService') as mock_monitoring:
        monitoring_instance = mock_monitoring.return_value
        monitoring_instance.log_prediction.return_value = True
        monitoring_instance.detect_drift.return_value = {
            'drift_detected': False,
            'drift_score': 0.15,
            'threshold': 0.3
        }
        monitoring_instance.get_model_metrics.return_value = {
            'predictions_count': 1000,
            'avg_confidence': 0.85,
            'error_rate': 0.05
        }
        yield monitoring_instance


# Database fixtures
@pytest.fixture
def test_db_engine():
    """Create test database engine."""
    engine = create_engine(
        "sqlite:///test.db",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    yield engine
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=test_db_engine
    )
    session = TestingSessionLocal()
    yield session
    session.close()


# Performance testing fixtures
@pytest.fixture
def large_dataset():
    """Generate large dataset for performance testing."""
    size = 10000
    return pd.DataFrame({
        'material_type': np.random.choice(['steel', 'aluminum', 'plastic'], size),
        'grade': np.random.choice(['A36', '6061', 'ABS'], size),
        'thickness': np.random.uniform(1, 50, size),
        'width': np.random.uniform(10, 500, size),
        'length': np.random.uniform(10, 1000, size),
        'quantity': np.random.randint(1, 5000, size),
        'price': np.random.normal(10, 3, size)
    })


@pytest.fixture
def performance_test_data():
    """Data for performance testing."""
    return {
        'concurrent_requests': 100,
        'request_timeout': 5.0,
        'expected_rps': 50,  # requests per second
        'max_response_time': 200,  # milliseconds
    }


# Security testing fixtures
@pytest.fixture
def malicious_payloads():
    """Common malicious payloads for security testing."""
    return [
        # SQL injection attempts
        "'; DROP TABLE users; --",
        "1' OR '1'='1",
        
        # XSS attempts
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        
        # Command injection
        "; cat /etc/passwd",
        "| whoami",
        
        # Path traversal
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        
        # Large payloads
        "A" * 10000,
        
        # Invalid JSON
        '{"incomplete": }',
        '{"unclosed": "string}',
    ]


@pytest.fixture
def security_test_headers():
    """Headers for security testing."""
    return {
        'X-Forwarded-For': '127.0.0.1',
        'User-Agent': 'SecurityTest/1.0',
        'X-Real-IP': '192.168.1.1',
    }


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Clear any test data, reset mocks, etc.
    pass


@pytest.fixture(scope="session", autouse=True)
def cleanup_after_session():
    """Cleanup after entire test session."""
    yield
    # Clean up test files, databases, etc.
    import os
    test_files = ['test.db', 'test_model.pkl']
    for file in test_files:
        if os.path.exists(file):
            os.remove(file)