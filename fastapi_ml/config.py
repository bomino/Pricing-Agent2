"""
Configuration for FastAPI ML Service
"""
import os
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "AI Pricing Agent - ML Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ML_SERVICE_JWT_SECRET: str = "ml-service-jwt-secret"
    ALLOWED_HOSTS: List[str] = ["*"]
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    
    # Database
    DATABASE_URL: str = "postgresql://pricing_user:password@localhost:5432/pricing_agent"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_TIMEOUT: int = 30
    
    # ML Models
    MODEL_STORAGE_PATH: str = "./ml_artifacts/models"
    MODEL_CACHE_TTL: int = 3600  # seconds
    MODEL_PREDICTION_TIMEOUT: int = 30  # seconds
    MAX_BATCH_SIZE: int = 1000
    
    # Feature Store
    FEATURE_STORE_ENABLED: bool = False
    FEATURE_STORE_URL: Optional[str] = None
    
    # MLflow
    MLFLOW_TRACKING_URI: str = "sqlite:///mlruns.db"
    MLFLOW_EXPERIMENT_NAME: str = "pricing_agent"
    MLFLOW_ARTIFACT_ROOT: Optional[str] = None
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"
    STRUCTURED_LOGGING: bool = True
    
    # Performance
    WORKER_PROCESSES: int = 1
    MAX_CONNECTIONS: int = 1000
    KEEP_ALIVE: int = 65
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # Caching
    PREDICTION_CACHE_TTL: int = 300  # 5 minutes
    FEATURE_CACHE_TTL: int = 600     # 10 minutes
    
    # External Services
    DJANGO_SERVICE_URL: str = "http://localhost:8000"
    DJANGO_SERVICE_TIMEOUT: int = 30
    
    # Data Sources
    MARKET_DATA_ENABLED: bool = False
    MARKET_DATA_API_KEY: Optional[str] = None
    MARKET_DATA_UPDATE_INTERVAL: int = 3600  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        },
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if settings.STRUCTURED_LOGGING else "standard",
            "level": settings.LOG_LEVEL,
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "ml_service.log",
            "formatter": "json" if settings.STRUCTURED_LOGGING else "standard",
            "level": settings.LOG_LEVEL,
        },
    },
    "loggers": {
        "": {  # Root logger
            "handlers": ["console", "file"],
            "level": settings.LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "httpx": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}


# Model configuration
MODEL_CONFIG = {
    "price_predictor": {
        "type": "lightgbm",
        "features": [
            "material_category",
            "supplier_rating",
            "quantity",
            "historical_avg_price",
            "market_trend",
            "seasonality",
        ],
        "target": "price",
        "preprocessing": {
            "scaler": "StandardScaler",
            "categorical_encoding": "LabelEncoder",
        },
        "hyperparameters": {
            "n_estimators": 100,
            "learning_rate": 0.1,
            "max_depth": 6,
            "num_leaves": 31,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "min_child_samples": 20,
        },
        "performance_thresholds": {
            "min_accuracy": 0.85,
            "max_mae": 0.1,
            "max_rmse": 0.15,
        }
    },
    "anomaly_detector": {
        "type": "isolation_forest",
        "features": [
            "price_per_unit",
            "supplier_deviation",
            "quantity_bracket",
            "time_features",
        ],
        "hyperparameters": {
            "n_estimators": 100,
            "contamination": 0.1,
            "random_state": 42,
        },
        "performance_thresholds": {
            "min_precision": 0.8,
            "min_recall": 0.7,
        }
    },
    "demand_forecaster": {
        "type": "prophet",
        "features": [
            "ds",  # datestamp
            "y",   # demand
        ],
        "hyperparameters": {
            "seasonality_mode": "multiplicative",
            "yearly_seasonality": True,
            "weekly_seasonality": True,
            "daily_seasonality": False,
            "holidays_prior_scale": 10.0,
            "seasonality_prior_scale": 10.0,
            "changepoint_prior_scale": 0.05,
        },
        "performance_thresholds": {
            "max_mape": 0.15,  # Mean Absolute Percentage Error
            "min_r2": 0.8,
        }
    }
}


# Feature engineering configuration
FEATURE_CONFIG = {
    "time_features": [
        "year",
        "month",
        "day_of_week",
        "quarter",
        "is_holiday",
        "is_weekend",
    ],
    "price_features": [
        "price_lag_1",
        "price_lag_7",
        "price_lag_30",
        "price_rolling_mean_7",
        "price_rolling_mean_30",
        "price_rolling_std_7",
        "price_rolling_std_30",
    ],
    "supplier_features": [
        "supplier_rating",
        "supplier_avg_price",
        "supplier_price_volatility",
        "supplier_delivery_score",
    ],
    "market_features": [
        "commodity_price_index",
        "inflation_rate",
        "exchange_rate",
        "market_volatility",
    ],
    "categorical_features": [
        "material_category",
        "supplier_type",
        "region",
        "payment_terms",
    ],
}