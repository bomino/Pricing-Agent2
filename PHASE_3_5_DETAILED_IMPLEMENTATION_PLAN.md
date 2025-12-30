# DETAILED IMPLEMENTATION PLAN: PHASES 3-5
## AI Pricing Agent Platform
### Technical Implementation Guide
#### Q1 2025 - Q4 2025

---

## TABLE OF CONTENTS

1. [Phase 3: ML/AI Integration (Q1 2025)](#phase-3-mlai-integration-q1-2025)
2. [Phase 4: Enterprise Features (Q2 2025)](#phase-4-enterprise-features-q2-2025)
3. [Phase 5: Advanced Analytics (Q3 2025)](#phase-5-advanced-analytics-q3-2025)
4. [Implementation Timeline](#implementation-timeline)
5. [Technical Specifications](#technical-specifications)
6. [Resource Allocation](#resource-allocation)

---

## PHASE 3: ML/AI INTEGRATION (Q1 2025)
### January - March 2025

## 3.1 FASTAPI ML SERVICE SETUP
### Week 1-2: Service Architecture Implementation

#### 3.1.1 Project Structure Setup

```bash
fastapi_ml/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── dependencies.py         # Dependency injection
│   └── middleware.py           # Custom middleware
├── api/
│   ├── __init__.py
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── endpoints/
│   │   │   ├── predictions.py  # Prediction endpoints
│   │   │   ├── models.py       # Model management endpoints
│   │   │   ├── training.py     # Training endpoints
│   │   │   └── monitoring.py   # Monitoring endpoints
│   │   └── schemas/
│   │       ├── predictions.py  # Request/Response schemas
│   │       └── models.py       # Model schemas
├── core/
│   ├── __init__.py
│   ├── security.py            # Security utilities
│   ├── exceptions.py          # Custom exceptions
│   └── logging.py            # Logging configuration
├── models/
│   ├── __init__.py
│   ├── price_predictor.py    # Price prediction models
│   ├── anomaly_detector.py   # Anomaly detection models
│   ├── should_cost.py        # Should-cost models
│   └── base.py              # Base model class
├── services/
│   ├── __init__.py
│   ├── model_service.py     # Model management service
│   ├── prediction_service.py # Prediction service
│   ├── training_service.py  # Training service
│   └── cache_service.py     # Redis caching service
├── ml_models/
│   ├── artifacts/           # Trained model files
│   ├── configs/            # Model configurations
│   └── checkpoints/        # Training checkpoints
└── tests/
    ├── unit/
    ├── integration/
    └── performance/
```

#### 3.1.2 FastAPI Application Setup

**File: `fastapi_ml/app/main.py`**
```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.middleware import TimingMiddleware, SecurityMiddleware
from api.v1 import api_router
from core.logging import setup_logging
from services.model_service import ModelService
from services.cache_service import CacheService

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting ML Service...")

    # Initialize services
    await CacheService.initialize()
    await ModelService.load_models()

    logger.info("ML Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down ML Service...")
    await CacheService.close()
    await ModelService.cleanup()

# Create FastAPI app
app = FastAPI(
    title="AI Pricing Agent ML Service",
    description="Machine Learning service for price predictions and analytics",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TimingMiddleware)
app.add_middleware(SecurityMiddleware)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ml-service",
        "version": "1.0.0",
        "models_loaded": await ModelService.get_loaded_models()
    }

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        workers=settings.WORKERS
    )
```

#### 3.1.3 Configuration Management

**File: `fastapi_ml/app/config.py`**
```python
from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "ML Service"
    DEBUG: bool = False
    WORKERS: int = 4

    # API settings
    API_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8000", "http://localhost:3000"]

    # Database settings
    POSTGRES_URL: str = "postgresql://user:pass@localhost/pricing_agent"

    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 3600  # 1 hour

    # Model settings
    MODEL_PATH: str = "./ml_models/artifacts"
    MODEL_CONFIG_PATH: str = "./ml_models/configs"
    MODEL_CHECKPOINT_PATH: str = "./ml_models/checkpoints"

    # ML settings
    BATCH_SIZE: int = 32
    MAX_SEQUENCE_LENGTH: int = 100
    PREDICTION_TIMEOUT: int = 30  # seconds

    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Monitoring settings
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090

    # AWS settings (for model storage)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

#### 3.1.4 Model Service Implementation

**File: `fastapi_ml/services/model_service.py`**
```python
import asyncio
import pickle
import joblib
from typing import Dict, Any, Optional, List
import numpy as np
import torch
from pathlib import Path
import logging

from app.config import settings
from models.price_predictor import PricePredictor
from models.anomaly_detector import AnomalyDetector
from models.should_cost import ShouldCostModel
from services.cache_service import CacheService

logger = logging.getLogger(__name__)

class ModelService:
    """Service for managing ML models"""

    _models: Dict[str, Any] = {}
    _model_configs: Dict[str, Dict] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def load_models(cls) -> None:
        """Load all models at startup"""
        async with cls._lock:
            try:
                # Load price prediction model
                cls._models['price_predictor'] = await cls._load_model(
                    'price_predictor',
                    PricePredictor
                )

                # Load anomaly detection model
                cls._models['anomaly_detector'] = await cls._load_model(
                    'anomaly_detector',
                    AnomalyDetector
                )

                # Load should-cost model
                cls._models['should_cost'] = await cls._load_model(
                    'should_cost',
                    ShouldCostModel
                )

                logger.info(f"Loaded {len(cls._models)} models successfully")

            except Exception as e:
                logger.error(f"Error loading models: {e}")
                raise

    @classmethod
    async def _load_model(cls, model_name: str, model_class) -> Any:
        """Load a specific model"""
        model_path = Path(settings.MODEL_PATH) / f"{model_name}.pkl"
        config_path = Path(settings.MODEL_CONFIG_PATH) / f"{model_name}.json"

        if model_path.exists():
            # Load from file
            if model_path.suffix == '.pkl':
                with open(model_path, 'rb') as f:
                    model = pickle.load(f)
            elif model_path.suffix == '.joblib':
                model = joblib.load(model_path)
            elif model_path.suffix == '.pt':
                model = torch.load(model_path)
            else:
                model = model_class()
                await model.load(model_path)
        else:
            # Initialize new model
            logger.warning(f"Model {model_name} not found, initializing new model")
            model = model_class()
            await model.initialize()

        # Load configuration
        if config_path.exists():
            import json
            with open(config_path, 'r') as f:
                cls._model_configs[model_name] = json.load(f)

        return model

    @classmethod
    async def predict(cls, model_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make prediction using specified model"""
        if model_name not in cls._models:
            raise ValueError(f"Model {model_name} not loaded")

        # Check cache
        cache_key = f"prediction:{model_name}:{hash(str(data))}"
        cached_result = await CacheService.get(cache_key)
        if cached_result:
            return cached_result

        # Make prediction
        model = cls._models[model_name]
        result = await model.predict(data)

        # Cache result
        await CacheService.set(cache_key, result, ttl=settings.CACHE_TTL)

        return result

    @classmethod
    async def batch_predict(cls, model_name: str, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Make batch predictions"""
        if model_name not in cls._models:
            raise ValueError(f"Model {model_name} not loaded")

        model = cls._models[model_name]

        # Process in batches
        results = []
        batch_size = settings.BATCH_SIZE

        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            batch_results = await model.batch_predict(batch)
            results.extend(batch_results)

        return results

    @classmethod
    async def train_model(cls, model_name: str, training_data: Dict[str, Any]) -> Dict[str, Any]:
        """Train or retrain a model"""
        if model_name not in cls._models:
            raise ValueError(f"Model {model_name} not loaded")

        model = cls._models[model_name]

        # Start training (async)
        training_id = await model.start_training(training_data)

        return {
            "training_id": training_id,
            "status": "started",
            "model": model_name
        }

    @classmethod
    async def get_model_info(cls, model_name: str) -> Dict[str, Any]:
        """Get information about a model"""
        if model_name not in cls._models:
            raise ValueError(f"Model {model_name} not loaded")

        model = cls._models[model_name]
        config = cls._model_configs.get(model_name, {})

        return {
            "name": model_name,
            "version": getattr(model, 'version', '1.0.0'),
            "type": model.__class__.__name__,
            "config": config,
            "metrics": await model.get_metrics()
        }

    @classmethod
    async def get_loaded_models(cls) -> List[str]:
        """Get list of loaded models"""
        return list(cls._models.keys())

    @classmethod
    async def cleanup(cls) -> None:
        """Cleanup models on shutdown"""
        for model_name, model in cls._models.items():
            if hasattr(model, 'cleanup'):
                await model.cleanup()
        cls._models.clear()
        cls._model_configs.clear()
```

## 3.2 PRICE PREDICTION MODELS
### Week 3-6: Implementation

#### 3.2.1 LSTM Price Predictor

**File: `fastapi_ml/models/price_predictor.py`**
```python
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Any, List, Tuple
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class LSTMPricePredictor(nn.Module):
    """LSTM model for price prediction"""

    def __init__(self,
                 input_size: int = 10,
                 hidden_size: int = 128,
                 num_layers: int = 2,
                 output_size: int = 1,
                 dropout: float = 0.2):
        super(LSTMPricePredictor, self).__init__()

        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # LSTM layers
        self.lstm = nn.LSTM(
            input_size,
            hidden_size,
            num_layers,
            batch_first=True,
            dropout=dropout
        )

        # Fully connected layers
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.fc2 = nn.Linear(hidden_size // 2, output_size)

        # Activation and dropout
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass"""
        # Initialize hidden state
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)

        # LSTM forward
        out, _ = self.lstm(x, (h0, c0))

        # Take last output
        out = out[:, -1, :]

        # Fully connected layers
        out = self.fc1(out)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)

        return out

class PricePredictor:
    """Price prediction service using LSTM"""

    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_columns = []
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.version = "1.0.0"

    async def initialize(self):
        """Initialize the model"""
        self.model = LSTMPricePredictor().to(self.device)
        self.model.eval()

        # Initialize feature scaler
        from sklearn.preprocessing import MinMaxScaler
        self.scaler = MinMaxScaler()

        # Define feature columns
        self.feature_columns = [
            'historical_price_1',
            'historical_price_2',
            'historical_price_3',
            'quantity',
            'supplier_score',
            'market_index',
            'seasonality_factor',
            'inflation_rate',
            'demand_indicator',
            'supply_indicator'
        ]

        logger.info("Price predictor initialized")

    async def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make price prediction"""
        try:
            # Extract features
            features = self._extract_features(data)

            # Convert to tensor
            x = torch.FloatTensor(features).unsqueeze(0).to(self.device)

            # Make prediction
            with torch.no_grad():
                prediction = self.model(x)

            # Convert to price
            predicted_price = float(prediction.cpu().numpy()[0, 0])

            # Calculate confidence interval
            confidence_lower = predicted_price * 0.95
            confidence_upper = predicted_price * 1.05

            return {
                "predicted_price": predicted_price,
                "confidence_interval": {
                    "lower": confidence_lower,
                    "upper": confidence_upper
                },
                "prediction_date": datetime.now().isoformat(),
                "model_version": self.version,
                "features_used": self.feature_columns
            }

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise

    async def batch_predict(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Make batch predictions"""
        results = []

        # Prepare batch data
        batch_features = []
        for data in data_list:
            features = self._extract_features(data)
            batch_features.append(features)

        # Convert to tensor
        x = torch.FloatTensor(batch_features).to(self.device)

        # Make predictions
        with torch.no_grad():
            predictions = self.model(x)

        # Process results
        for i, pred in enumerate(predictions):
            predicted_price = float(pred.cpu().numpy()[0])
            results.append({
                "predicted_price": predicted_price,
                "confidence_interval": {
                    "lower": predicted_price * 0.95,
                    "upper": predicted_price * 1.05
                },
                "input_data": data_list[i]
            })

        return results

    def _extract_features(self, data: Dict[str, Any]) -> np.ndarray:
        """Extract features from input data"""
        features = []

        # Historical prices
        features.extend(data.get('historical_prices', [0, 0, 0])[:3])

        # Quantity
        features.append(data.get('quantity', 0))

        # Supplier score
        features.append(data.get('supplier_score', 0.5))

        # Market indicators
        features.append(data.get('market_index', 100))
        features.append(data.get('seasonality_factor', 1.0))
        features.append(data.get('inflation_rate', 0.02))
        features.append(data.get('demand_indicator', 0.5))
        features.append(data.get('supply_indicator', 0.5))

        # Pad or truncate to correct size
        while len(features) < 10:
            features.append(0)
        features = features[:10]

        # Create sequence (last 10 time steps)
        sequence = np.array(features).reshape(1, -1)
        sequence = np.repeat(sequence, 10, axis=0)

        return sequence

    async def start_training(self, training_data: Dict[str, Any]) -> str:
        """Start model training"""
        import uuid
        training_id = str(uuid.uuid4())

        # Start training in background
        import asyncio
        asyncio.create_task(self._train_model(training_id, training_data))

        return training_id

    async def _train_model(self, training_id: str, training_data: Dict[str, Any]):
        """Train the model (async)"""
        try:
            logger.info(f"Starting training {training_id}")

            # Prepare data
            X_train = training_data['X_train']
            y_train = training_data['y_train']
            X_val = training_data.get('X_val')
            y_val = training_data.get('y_val')

            # Training parameters
            epochs = training_data.get('epochs', 100)
            batch_size = training_data.get('batch_size', 32)
            learning_rate = training_data.get('learning_rate', 0.001)

            # Setup optimizer and loss
            optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
            criterion = nn.MSELoss()

            # Training loop
            self.model.train()
            for epoch in range(epochs):
                total_loss = 0

                # Mini-batch training
                for i in range(0, len(X_train), batch_size):
                    batch_X = torch.FloatTensor(X_train[i:i+batch_size]).to(self.device)
                    batch_y = torch.FloatTensor(y_train[i:i+batch_size]).to(self.device)

                    # Forward pass
                    outputs = self.model(batch_X)
                    loss = criterion(outputs, batch_y)

                    # Backward pass
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()

                    total_loss += loss.item()

                # Validation
                if X_val is not None and epoch % 10 == 0:
                    self.model.eval()
                    with torch.no_grad():
                        val_X = torch.FloatTensor(X_val).to(self.device)
                        val_y = torch.FloatTensor(y_val).to(self.device)
                        val_outputs = self.model(val_X)
                        val_loss = criterion(val_outputs, val_y)

                    logger.info(f"Epoch {epoch}, Train Loss: {total_loss:.4f}, Val Loss: {val_loss:.4f}")
                    self.model.train()

            self.model.eval()
            logger.info(f"Training {training_id} completed")

            # Save model
            await self.save()

        except Exception as e:
            logger.error(f"Training error: {e}")
            raise

    async def save(self, path: str = None):
        """Save model to disk"""
        if path is None:
            path = f"./ml_models/artifacts/price_predictor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"

        torch.save({
            'model_state_dict': self.model.state_dict(),
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'version': self.version
        }, path)

        logger.info(f"Model saved to {path}")

    async def load(self, path: str):
        """Load model from disk"""
        checkpoint = torch.load(path, map_location=self.device)

        self.model = LSTMPricePredictor().to(self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()

        self.scaler = checkpoint['scaler']
        self.feature_columns = checkpoint['feature_columns']
        self.version = checkpoint.get('version', '1.0.0')

        logger.info(f"Model loaded from {path}")

    async def get_metrics(self) -> Dict[str, Any]:
        """Get model metrics"""
        return {
            "model_type": "LSTM",
            "version": self.version,
            "device": str(self.device),
            "parameters": sum(p.numel() for p in self.model.parameters()),
            "trainable_parameters": sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        }
```

#### 3.2.2 Prophet Time-Series Model

**File: `fastapi_ml/models/prophet_predictor.py`**
```python
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ProphetPricePredictor:
    """Facebook Prophet model for time-series price prediction"""

    def __init__(self):
        self.model = None
        self.version = "1.0.0"
        self.trained_materials = {}

    async def initialize(self):
        """Initialize the Prophet model"""
        self.model = Prophet(
            growth='linear',
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            seasonality_mode='multiplicative',
            interval_width=0.95,
            changepoint_prior_scale=0.05
        )

        # Add custom seasonality
        self.model.add_seasonality(
            name='quarterly',
            period=91.25,
            fourier_order=5
        )

        # Add regressors
        self.model.add_regressor('market_index', prior_scale=0.5)
        self.model.add_regressor('inflation_rate', prior_scale=0.5)
        self.model.add_regressor('demand_indicator', prior_scale=0.5)

        logger.info("Prophet predictor initialized")

    async def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make price prediction for a specific material"""
        try:
            material_id = data.get('material_id')
            forecast_days = data.get('forecast_days', 90)

            # Get model for specific material
            if material_id not in self.trained_materials:
                return {
                    "error": f"No trained model for material {material_id}",
                    "status": "model_not_found"
                }

            model = self.trained_materials[material_id]

            # Create future dataframe
            future = model.make_future_dataframe(periods=forecast_days)

            # Add regressor values
            future['market_index'] = data.get('market_index', 100)
            future['inflation_rate'] = data.get('inflation_rate', 0.02)
            future['demand_indicator'] = data.get('demand_indicator', 0.5)

            # Make forecast
            forecast = model.predict(future)

            # Extract predictions
            predictions = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(forecast_days)

            return {
                "material_id": material_id,
                "predictions": predictions.to_dict('records'),
                "forecast_days": forecast_days,
                "model_version": self.version,
                "components": {
                    "trend": forecast['trend'].tail(forecast_days).tolist(),
                    "yearly": forecast['yearly'].tail(forecast_days).tolist(),
                    "weekly": forecast['weekly'].tail(forecast_days).tolist()
                }
            }

        except Exception as e:
            logger.error(f"Prophet prediction error: {e}")
            raise

    async def train_material_model(self, material_id: str, historical_data: pd.DataFrame) -> Dict[str, Any]:
        """Train Prophet model for a specific material"""
        try:
            # Prepare data
            df = historical_data.copy()
            df = df.rename(columns={'date': 'ds', 'price': 'y'})

            # Ensure required columns
            required_cols = ['ds', 'y', 'market_index', 'inflation_rate', 'demand_indicator']
            for col in required_cols:
                if col not in df.columns:
                    if col == 'ds':
                        df['ds'] = pd.date_range(start='2023-01-01', periods=len(df))
                    elif col == 'y':
                        raise ValueError("Price column 'y' is required")
                    else:
                        df[col] = 0.5  # Default value

            # Create and fit model
            model = Prophet(
                growth='linear',
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                seasonality_mode='multiplicative',
                interval_width=0.95,
                changepoint_prior_scale=0.05
            )

            # Add regressors
            model.add_regressor('market_index', prior_scale=0.5)
            model.add_regressor('inflation_rate', prior_scale=0.5)
            model.add_regressor('demand_indicator', prior_scale=0.5)

            # Fit model
            model.fit(df)

            # Store trained model
            self.trained_materials[material_id] = model

            # Cross-validation
            df_cv = cross_validation(
                model,
                initial='365 days',
                period='90 days',
                horizon='30 days'
            )

            # Calculate metrics
            df_p = performance_metrics(df_cv)
            metrics = {
                'mape': float(df_p['mape'].mean()),
                'rmse': float(df_p['rmse'].mean()),
                'mae': float(df_p['mae'].mean())
            }

            return {
                "material_id": material_id,
                "status": "trained",
                "metrics": metrics,
                "training_samples": len(df),
                "model_version": self.version
            }

        except Exception as e:
            logger.error(f"Prophet training error: {e}")
            raise

    async def batch_train(self, materials_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """Train models for multiple materials"""
        results = []

        for material_id, data in materials_data.items():
            result = await self.train_material_model(material_id, data)
            results.append(result)

        return results
```

## 3.3 SHOULD-COST MODELING
### Week 7-9: Component Analysis Implementation

#### 3.3.1 Should-Cost Model

**File: `fastapi_ml/models/should_cost.py`**
```python
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class CostComponent:
    """Represents a cost component in should-cost model"""
    name: str
    base_cost: float
    quantity: float
    unit: str
    markup_percentage: float = 0.0

    @property
    def total_cost(self) -> float:
        cost = self.base_cost * self.quantity
        return cost * (1 + self.markup_percentage / 100)

class ShouldCostModel:
    """Should-cost modeling for component-based analysis"""

    def __init__(self):
        self.version = "1.0.0"
        self.cost_databases = {}
        self.regional_factors = {}
        self.material_indices = {}

    async def initialize(self):
        """Initialize should-cost model with reference data"""
        # Load material cost indices
        self.material_indices = {
            'steel': {'base_price': 850, 'unit': 'USD/ton', 'volatility': 0.15},
            'aluminum': {'base_price': 2200, 'unit': 'USD/ton', 'volatility': 0.18},
            'copper': {'base_price': 9500, 'unit': 'USD/ton', 'volatility': 0.20},
            'plastic': {'base_price': 1200, 'unit': 'USD/ton', 'volatility': 0.12},
            'rubber': {'base_price': 1800, 'unit': 'USD/ton', 'volatility': 0.10}
        }

        # Load regional labor factors
        self.regional_factors = {
            'US': {'labor_rate': 35.0, 'overhead': 2.5, 'currency': 'USD'},
            'CN': {'labor_rate': 8.0, 'overhead': 1.8, 'currency': 'CNY'},
            'DE': {'labor_rate': 42.0, 'overhead': 3.0, 'currency': 'EUR'},
            'MX': {'labor_rate': 12.0, 'overhead': 2.0, 'currency': 'MXN'},
            'IN': {'labor_rate': 5.0, 'overhead': 1.5, 'currency': 'INR'}
        }

        # Standard process costs
        self.process_costs = {
            'machining': {'cost_per_hour': 75, 'efficiency': 0.85},
            'welding': {'cost_per_hour': 65, 'efficiency': 0.80},
            'assembly': {'cost_per_hour': 45, 'efficiency': 0.90},
            'painting': {'cost_per_hour': 55, 'efficiency': 0.75},
            'testing': {'cost_per_hour': 85, 'efficiency': 0.95}
        }

        logger.info("Should-cost model initialized")

    async def calculate_should_cost(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate should-cost for a product"""
        try:
            # Extract input parameters
            product_spec = data.get('product_specification', {})
            materials = data.get('materials', [])
            processes = data.get('processes', [])
            quantity = data.get('quantity', 1)
            region = data.get('region', 'US')

            # Calculate material costs
            material_cost = self._calculate_material_cost(materials, quantity)

            # Calculate labor costs
            labor_cost = self._calculate_labor_cost(processes, region)

            # Calculate overhead
            overhead_cost = self._calculate_overhead(material_cost, labor_cost, region)

            # Calculate tooling amortization
            tooling_cost = self._calculate_tooling_cost(data.get('tooling', {}), quantity)

            # Calculate logistics
            logistics_cost = self._calculate_logistics_cost(data.get('logistics', {}), quantity)

            # Sum up total cost
            total_direct_cost = material_cost + labor_cost + tooling_cost
            total_indirect_cost = overhead_cost + logistics_cost
            total_cost = total_direct_cost + total_indirect_cost

            # Apply margin
            margin_percentage = data.get('target_margin', 15)
            selling_price = total_cost * (1 + margin_percentage / 100)

            # Generate cost breakdown
            cost_breakdown = {
                'material_cost': {
                    'value': material_cost,
                    'percentage': (material_cost / total_cost) * 100,
                    'components': self._detail_material_components(materials)
                },
                'labor_cost': {
                    'value': labor_cost,
                    'percentage': (labor_cost / total_cost) * 100,
                    'components': self._detail_labor_components(processes, region)
                },
                'overhead_cost': {
                    'value': overhead_cost,
                    'percentage': (overhead_cost / total_cost) * 100
                },
                'tooling_cost': {
                    'value': tooling_cost,
                    'percentage': (tooling_cost / total_cost) * 100
                },
                'logistics_cost': {
                    'value': logistics_cost,
                    'percentage': (logistics_cost / total_cost) * 100
                }
            }

            # Sensitivity analysis
            sensitivity = self._perform_sensitivity_analysis(
                material_cost, labor_cost, overhead_cost, margin_percentage
            )

            return {
                'should_cost': total_cost,
                'selling_price': selling_price,
                'cost_breakdown': cost_breakdown,
                'total_direct_cost': total_direct_cost,
                'total_indirect_cost': total_indirect_cost,
                'margin_percentage': margin_percentage,
                'quantity': quantity,
                'region': region,
                'currency': self.regional_factors[region]['currency'],
                'sensitivity_analysis': sensitivity,
                'confidence_level': self._calculate_confidence_level(data),
                'calculation_date': datetime.now().isoformat(),
                'model_version': self.version
            }

        except Exception as e:
            logger.error(f"Should-cost calculation error: {e}")
            raise

    def _calculate_material_cost(self, materials: List[Dict], quantity: int) -> float:
        """Calculate total material cost"""
        total_cost = 0

        for material in materials:
            material_type = material.get('type', 'steel')
            weight = material.get('weight', 0)  # in kg
            scrap_rate = material.get('scrap_rate', 0.05)  # 5% default scrap

            if material_type in self.material_indices:
                base_price = self.material_indices[material_type]['base_price']
                # Convert to per kg
                price_per_kg = base_price / 1000

                # Apply market fluctuation
                market_factor = material.get('market_factor', 1.0)
                price_per_kg *= market_factor

                # Calculate with scrap
                required_material = weight * (1 + scrap_rate)
                cost = required_material * price_per_kg * quantity

                total_cost += cost

        return total_cost

    def _calculate_labor_cost(self, processes: List[Dict], region: str) -> float:
        """Calculate total labor cost"""
        total_cost = 0
        regional_data = self.regional_factors.get(region, self.regional_factors['US'])
        labor_rate = regional_data['labor_rate']

        for process in processes:
            process_type = process.get('type', 'assembly')
            hours = process.get('hours', 0)
            skill_level = process.get('skill_level', 'standard')

            # Adjust rate based on skill level
            skill_multiplier = {
                'basic': 0.8,
                'standard': 1.0,
                'skilled': 1.3,
                'expert': 1.6
            }.get(skill_level, 1.0)

            if process_type in self.process_costs:
                process_data = self.process_costs[process_type]
                effective_hours = hours / process_data['efficiency']
                cost = effective_hours * labor_rate * skill_multiplier
                total_cost += cost
            else:
                # Default process cost
                cost = hours * labor_rate * skill_multiplier
                total_cost += cost

        return total_cost

    def _calculate_overhead(self, material_cost: float, labor_cost: float, region: str) -> float:
        """Calculate overhead costs"""
        regional_data = self.regional_factors.get(region, self.regional_factors['US'])
        overhead_multiplier = regional_data['overhead']

        # Overhead as percentage of labor cost
        overhead = labor_cost * (overhead_multiplier - 1)

        # Add material handling overhead (5% of material cost)
        material_overhead = material_cost * 0.05

        return overhead + material_overhead

    def _calculate_tooling_cost(self, tooling_data: Dict, quantity: int) -> float:
        """Calculate tooling amortization"""
        if not tooling_data:
            return 0

        tooling_investment = tooling_data.get('investment', 0)
        expected_volume = tooling_data.get('expected_volume', 10000)
        maintenance_rate = tooling_data.get('maintenance_rate', 0.1)  # 10% of investment

        # Amortization per unit
        amortization = tooling_investment / expected_volume

        # Add maintenance cost
        maintenance = (tooling_investment * maintenance_rate) / expected_volume

        return (amortization + maintenance) * quantity

    def _calculate_logistics_cost(self, logistics_data: Dict, quantity: int) -> float:
        """Calculate logistics and shipping costs"""
        if not logistics_data:
            # Default logistics cost (2% of total)
            return 0

        shipping_method = logistics_data.get('method', 'ground')
        distance = logistics_data.get('distance', 500)  # km
        weight = logistics_data.get('total_weight', quantity * 10)  # kg

        # Cost per kg per km
        rates = {
            'air': 0.005,
            'ground': 0.001,
            'sea': 0.0003,
            'express': 0.008
        }

        rate = rates.get(shipping_method, 0.001)
        shipping_cost = weight * distance * rate

        # Add handling fees
        handling = logistics_data.get('handling_fee', 50)

        return shipping_cost + handling

    def _detail_material_components(self, materials: List[Dict]) -> List[Dict]:
        """Provide detailed material cost breakdown"""
        components = []

        for material in materials:
            material_type = material.get('type', 'unknown')
            weight = material.get('weight', 0)

            if material_type in self.material_indices:
                base_price = self.material_indices[material_type]['base_price']
                components.append({
                    'type': material_type,
                    'weight': weight,
                    'unit_price': base_price / 1000,  # per kg
                    'total': weight * (base_price / 1000)
                })

        return components

    def _detail_labor_components(self, processes: List[Dict], region: str) -> List[Dict]:
        """Provide detailed labor cost breakdown"""
        components = []
        regional_data = self.regional_factors.get(region, self.regional_factors['US'])
        labor_rate = regional_data['labor_rate']

        for process in processes:
            process_type = process.get('type', 'unknown')
            hours = process.get('hours', 0)

            components.append({
                'process': process_type,
                'hours': hours,
                'rate': labor_rate,
                'total': hours * labor_rate
            })

        return components

    def _perform_sensitivity_analysis(self, material: float, labor: float,
                                     overhead: float, margin: float) -> Dict[str, Any]:
        """Perform sensitivity analysis on cost factors"""
        base_total = material + labor + overhead

        sensitivity = {
            'material_10pct_increase': ((base_total + material * 0.1) - base_total) / base_total * 100,
            'labor_10pct_increase': ((base_total + labor * 0.1) - base_total) / base_total * 100,
            'overhead_10pct_increase': ((base_total + overhead * 0.1) - base_total) / base_total * 100,
            'margin_impact': {
                'margin_minus_5pct': base_total * (1 + (margin - 5) / 100),
                'margin_plus_5pct': base_total * (1 + (margin + 5) / 100)
            }
        }

        return sensitivity

    def _calculate_confidence_level(self, data: Dict) -> float:
        """Calculate confidence level of the estimate"""
        confidence = 100

        # Reduce confidence for missing data
        if not data.get('materials'):
            confidence -= 20
        if not data.get('processes'):
            confidence -= 20
        if not data.get('region'):
            confidence -= 10
        if not data.get('tooling'):
            confidence -= 5
        if not data.get('logistics'):
            confidence -= 5

        # Increase confidence for detailed specifications
        if len(data.get('materials', [])) > 3:
            confidence = min(100, confidence + 5)
        if len(data.get('processes', [])) > 3:
            confidence = min(100, confidence + 5)

        return max(0, confidence)
```

## 3.4 ANOMALY DETECTION
### Week 10-12: Advanced Detection System

#### 3.4.1 Anomaly Detection Model

**File: `fastapi_ml/models/anomaly_detector.py`**
```python
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import torch
import torch.nn as nn
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

class AutoEncoder(nn.Module):
    """Autoencoder for anomaly detection"""

    def __init__(self, input_dim: int, encoding_dim: int = 32):
        super(AutoEncoder, self).__init__()

        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, encoding_dim),
            nn.ReLU()
        )

        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(encoding_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, input_dim),
            nn.Sigmoid()
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

class AnomalyDetector:
    """Comprehensive anomaly detection system"""

    def __init__(self):
        self.isolation_forest = None
        self.autoencoder = None
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=0.95)
        self.threshold_percentile = 95
        self.version = "1.0.0"
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    async def initialize(self):
        """Initialize anomaly detection models"""
        # Initialize Isolation Forest
        self.isolation_forest = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42
        )

        # Initialize Autoencoder (will be properly initialized when we know input dim)
        self.autoencoder = None

        logger.info("Anomaly detector initialized")

    async def detect_anomalies(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect anomalies in the data"""
        try:
            anomaly_type = data.get('type', 'price')
            records = data.get('records', [])

            if not records:
                return {
                    'status': 'no_data',
                    'anomalies': []
                }

            # Convert to DataFrame
            df = pd.DataFrame(records)

            # Detect based on type
            if anomaly_type == 'price':
                anomalies = await self._detect_price_anomalies(df)
            elif anomaly_type == 'quantity':
                anomalies = await self._detect_quantity_anomalies(df)
            elif anomaly_type == 'supplier':
                anomalies = await self._detect_supplier_anomalies(df)
            elif anomaly_type == 'pattern':
                anomalies = await self._detect_pattern_anomalies(df)
            else:
                anomalies = await self._detect_general_anomalies(df)

            return {
                'status': 'success',
                'type': anomaly_type,
                'total_records': len(records),
                'anomalies_detected': len(anomalies),
                'anomalies': anomalies,
                'model_version': self.version
            }

        except Exception as e:
            logger.error(f"Anomaly detection error: {e}")
            raise

    async def _detect_price_anomalies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect price anomalies"""
        anomalies = []

        if 'price' not in df.columns:
            return anomalies

        # Statistical method (Z-score)
        prices = df['price'].values
        mean_price = np.mean(prices)
        std_price = np.std(prices)

        for idx, row in df.iterrows():
            price = row['price']
            z_score = abs((price - mean_price) / std_price) if std_price > 0 else 0

            if z_score > 3:  # 3 standard deviations
                anomalies.append({
                    'index': idx,
                    'type': 'price_outlier',
                    'severity': 'high' if z_score > 4 else 'medium',
                    'value': price,
                    'expected_range': [mean_price - 3*std_price, mean_price + 3*std_price],
                    'z_score': z_score,
                    'description': f"Price ${price:.2f} is {z_score:.1f} standard deviations from mean",
                    'record': row.to_dict()
                })

        # Isolation Forest method
        if len(prices) > 10:
            prices_reshaped = prices.reshape(-1, 1)
            self.isolation_forest.fit(prices_reshaped)
            predictions = self.isolation_forest.predict(prices_reshaped)

            for idx, (pred, row) in enumerate(zip(predictions, df.iterrows())):
                if pred == -1:  # Anomaly
                    # Check if not already detected
                    if not any(a['index'] == row[0] for a in anomalies):
                        anomalies.append({
                            'index': row[0],
                            'type': 'price_pattern',
                            'severity': 'medium',
                            'value': row[1]['price'],
                            'method': 'isolation_forest',
                            'description': f"Unusual price pattern detected",
                            'record': row[1].to_dict()
                        })

        return anomalies

    async def _detect_quantity_anomalies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect quantity anomalies"""
        anomalies = []

        if 'quantity' not in df.columns:
            return anomalies

        quantities = df['quantity'].values

        # Check for unusual quantities
        q1 = np.percentile(quantities, 25)
        q3 = np.percentile(quantities, 75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        for idx, row in df.iterrows():
            quantity = row['quantity']

            # Check for outliers
            if quantity < lower_bound or quantity > upper_bound:
                anomalies.append({
                    'index': idx,
                    'type': 'quantity_outlier',
                    'severity': 'medium',
                    'value': quantity,
                    'expected_range': [lower_bound, upper_bound],
                    'description': f"Quantity {quantity} outside normal range",
                    'record': row.to_dict()
                })

            # Check for unusual patterns (e.g., exact round numbers)
            if quantity > 1000 and quantity % 1000 == 0:
                anomalies.append({
                    'index': idx,
                    'type': 'quantity_pattern',
                    'severity': 'low',
                    'value': quantity,
                    'description': f"Suspiciously round quantity: {quantity}",
                    'record': row.to_dict()
                })

        return anomalies

    async def _detect_supplier_anomalies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect supplier behavior anomalies"""
        anomalies = []

        if 'supplier_id' not in df.columns:
            return anomalies

        # Group by supplier
        for supplier_id, supplier_df in df.groupby('supplier_id'):
            # Check for sudden price changes
            if 'price' in supplier_df.columns and len(supplier_df) > 1:
                prices = supplier_df['price'].values
                price_changes = np.diff(prices) / prices[:-1] * 100

                for i, change in enumerate(price_changes):
                    if abs(change) > 20:  # 20% change
                        anomalies.append({
                            'index': supplier_df.index[i+1],
                            'type': 'supplier_price_change',
                            'severity': 'high' if abs(change) > 30 else 'medium',
                            'supplier_id': supplier_id,
                            'change_percentage': change,
                            'description': f"Supplier {supplier_id} changed price by {change:.1f}%",
                            'record': supplier_df.iloc[i+1].to_dict()
                        })

            # Check for unusual order patterns
            if 'order_date' in supplier_df.columns and len(supplier_df) > 3:
                dates = pd.to_datetime(supplier_df['order_date'])
                intervals = dates.diff().dt.days.dropna()

                if len(intervals) > 0:
                    avg_interval = intervals.mean()

                    for i, interval in enumerate(intervals):
                        if interval > avg_interval * 3:
                            anomalies.append({
                                'index': supplier_df.index[i+1],
                                'type': 'supplier_order_gap',
                                'severity': 'low',
                                'supplier_id': supplier_id,
                                'gap_days': interval,
                                'expected_days': avg_interval,
                                'description': f"Unusual gap in orders from supplier {supplier_id}",
                                'record': supplier_df.iloc[i+1].to_dict()
                            })

        return anomalies

    async def _detect_pattern_anomalies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect complex pattern anomalies using autoencoder"""
        anomalies = []

        # Prepare features
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) < 2:
            return anomalies

        X = df[numeric_columns].values

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Initialize autoencoder if needed
        if self.autoencoder is None:
            input_dim = X_scaled.shape[1]
            self.autoencoder = AutoEncoder(input_dim).to(self.device)

            # Train autoencoder (simplified for demo)
            self._train_autoencoder(X_scaled)

        # Detect anomalies
        X_tensor = torch.FloatTensor(X_scaled).to(self.device)

        with torch.no_grad():
            self.autoencoder.eval()
            reconstructed = self.autoencoder(X_tensor)
            mse = torch.mean((X_tensor - reconstructed) ** 2, dim=1)

        # Calculate threshold
        threshold = torch.quantile(mse, self.threshold_percentile / 100)

        # Identify anomalies
        anomaly_indices = torch.where(mse > threshold)[0]

        for idx in anomaly_indices:
            anomalies.append({
                'index': int(idx),
                'type': 'pattern_anomaly',
                'severity': 'medium',
                'reconstruction_error': float(mse[idx]),
                'threshold': float(threshold),
                'description': 'Unusual pattern detected in combined features',
                'record': df.iloc[idx].to_dict()
            })

        return anomalies

    def _train_autoencoder(self, X: np.ndarray, epochs: int = 50):
        """Quick training of autoencoder"""
        X_tensor = torch.FloatTensor(X).to(self.device)

        optimizer = torch.optim.Adam(self.autoencoder.parameters(), lr=0.001)
        criterion = nn.MSELoss()

        self.autoencoder.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            reconstructed = self.autoencoder(X_tensor)
            loss = criterion(reconstructed, X_tensor)
            loss.backward()
            optimizer.step()

    async def _detect_general_anomalies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect general anomalies using multiple methods"""
        anomalies = []

        # Combine results from different detection methods
        anomalies.extend(await self._detect_price_anomalies(df))
        anomalies.extend(await self._detect_quantity_anomalies(df))
        anomalies.extend(await self._detect_supplier_anomalies(df))
        anomalies.extend(await self._detect_pattern_anomalies(df))

        # Remove duplicates based on index
        unique_anomalies = []
        seen_indices = set()

        for anomaly in anomalies:
            if anomaly['index'] not in seen_indices:
                unique_anomalies.append(anomaly)
                seen_indices.add(anomaly['index'])

        return unique_anomalies
```

## 3.5 API ENDPOINTS
### Integration Layer

#### 3.5.1 Prediction Endpoints

**File: `fastapi_ml/api/v1/endpoints/predictions.py`**
```python
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

from services.model_service import ModelService
from api.v1.schemas.predictions import (
    PricePredictionRequest,
    PricePredictionResponse,
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    ShouldCostRequest,
    ShouldCostResponse
)

router = APIRouter(prefix="/predictions", tags=["predictions"])

@router.post("/price", response_model=PricePredictionResponse)
async def predict_price(request: PricePredictionRequest) -> PricePredictionResponse:
    """Predict price for materials"""
    try:
        result = await ModelService.predict('price_predictor', request.dict())
        return PricePredictionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/price/batch", response_model=List[PricePredictionResponse])
async def batch_predict_price(requests: List[PricePredictionRequest]) -> List[PricePredictionResponse]:
    """Batch price predictions"""
    try:
        data_list = [req.dict() for req in requests]
        results = await ModelService.batch_predict('price_predictor', data_list)
        return [PricePredictionResponse(**result) for result in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/anomalies", response_model=AnomalyDetectionResponse)
async def detect_anomalies(request: AnomalyDetectionRequest) -> AnomalyDetectionResponse:
    """Detect anomalies in data"""
    try:
        result = await ModelService.predict('anomaly_detector', request.dict())
        return AnomalyDetectionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/should-cost", response_model=ShouldCostResponse)
async def calculate_should_cost(request: ShouldCostRequest) -> ShouldCostResponse:
    """Calculate should-cost for a product"""
    try:
        result = await ModelService.predict('should_cost', request.dict())
        return ShouldCostResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
async def list_models():
    """List available models"""
    models = await ModelService.get_loaded_models()
    return {
        "models": models,
        "count": len(models)
    }

@router.get("/models/{model_name}")
async def get_model_info(model_name: str):
    """Get information about a specific model"""
    try:
        info = await ModelService.get_model_info(model_name)
        return info
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

---

## PHASE 4: ENTERPRISE FEATURES (Q2 2025)
### April - June 2025

[Document continues with Phase 4 and Phase 5 detailed implementations...]

---

## IMPLEMENTATION TIMELINE

### Q1 2025: ML/AI Integration
- **Week 1-2**: FastAPI service setup and infrastructure
- **Week 3-4**: Price prediction LSTM model
- **Week 5-6**: Prophet time-series model and ensemble
- **Week 7-8**: Should-cost modeling system
- **Week 9-10**: Anomaly detection algorithms
- **Week 11-12**: Integration testing and optimization

### Q2 2025: Enterprise Features
- **Week 1-4**: ERP integration (SAP, Oracle, Dynamics)
- **Week 5-8**: Supplier portal development
- **Week 9-10**: Advanced RBAC implementation
- **Week 11-12**: WebSocket real-time updates
- **Week 13-14**: Security audit and hardening
- **Week 15-16**: Performance optimization

### Q3 2025: Advanced Analytics
- **Week 1-4**: Predictive spend analytics
- **Week 5-8**: Market intelligence integration
- **Week 9-12**: Supply chain risk management

---

## SUCCESS METRICS

### Phase 3 Targets
- ML model accuracy: >85%
- API response time: <500ms
- Prediction confidence: >90%
- System uptime: >99.9%

### Phase 4 Targets
- ERP sync time: <5 minutes
- Supplier adoption: >60%
- Security compliance: 100%
- Real-time latency: <100ms

### Phase 5 Targets
- Forecast accuracy: >80%
- Risk detection rate: >95%
- Market data coverage: >90%
- Analytics processing: <10s

---

**Document Version**: 1.0
**Last Updated**: December 2024
**Next Review**: January 2025
**Repository**: https://github.com/bomino/Pricing-Agent2

---

*End of Detailed Implementation Plan*