"""
Model Registry Service - Manages ML model lifecycle
"""
import asyncio
import os
import pickle
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import structlog
import mlflow
import mlflow.pyfunc
from mlflow.tracking import MlflowClient
from redis import Redis
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ..config import settings, MODEL_CONFIG

logger = structlog.get_logger()


class ModelMetadata:
    """Model metadata container"""
    
    def __init__(self, 
                 name: str,
                 version: str,
                 model_type: str,
                 created_at: datetime,
                 performance_metrics: Dict[str, float],
                 features: List[str],
                 model_path: str = None,
                 mlflow_run_id: str = None):
        self.name = name
        self.version = version
        self.model_type = model_type
        self.created_at = created_at
        self.performance_metrics = performance_metrics
        self.features = features
        self.model_path = model_path
        self.mlflow_run_id = mlflow_run_id
        self.last_used = datetime.utcnow()
        self.prediction_count = 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "version": self.version,
            "model_type": self.model_type,
            "created_at": self.created_at.isoformat(),
            "performance_metrics": self.performance_metrics,
            "features": self.features,
            "model_path": self.model_path,
            "mlflow_run_id": self.mlflow_run_id,
            "last_used": self.last_used.isoformat(),
            "prediction_count": self.prediction_count
        }


class ModelRegistry:
    """
    Production-ready model registry with caching, versioning, and health monitoring
    """
    
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.metadata: Dict[str, ModelMetadata] = {}
        self.redis_client: Optional[Redis] = None
        self.mlflow_client = MlflowClient(settings.MLFLOW_TRACKING_URI)
        self.model_cache_ttl = settings.MODEL_CACHE_TTL
        self.storage_path = Path(settings.MODEL_STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Model performance thresholds
        self.performance_thresholds = {
            model_name: config.get("performance_thresholds", {})
            for model_name, config in MODEL_CONFIG.items()
        }
        
        logger.info("Model registry initialized", storage_path=str(self.storage_path))
    
    async def initialize_redis(self, redis_client: Redis):
        """Initialize Redis connection"""
        self.redis_client = redis_client
        logger.info("Redis initialized for model registry")
    
    async def load_models(self) -> None:
        """Load all models from storage and MLflow"""
        try:
            # Load from MLflow first
            await self._load_from_mlflow()
            
            # Load local models as fallback
            await self._load_local_models()
            
            logger.info(
                "Models loaded successfully",
                total_models=len(self.models),
                model_names=list(self.models.keys())
            )
            
        except Exception as e:
            logger.error("Failed to load models", error=str(e), exc_info=True)
            raise
    
    async def _load_from_mlflow(self) -> None:
        """Load models from MLflow"""
        try:
            # Get latest versions of registered models
            for model_name in MODEL_CONFIG.keys():
                try:
                    # Get latest production model
                    model_version = self.mlflow_client.get_latest_versions(
                        model_name,
                        stages=["Production"]
                    )
                    
                    if not model_version:
                        # Try staging if no production model
                        model_version = self.mlflow_client.get_latest_versions(
                            model_name,
                            stages=["Staging"]
                        )
                    
                    if model_version:
                        version_info = model_version[0]
                        model_uri = f"models:/{model_name}/{version_info.version}"
                        
                        # Load model
                        model = mlflow.pyfunc.load_model(model_uri)
                        
                        # Get run info for metadata
                        run = self.mlflow_client.get_run(version_info.run_id)
                        
                        # Create metadata
                        metadata = ModelMetadata(
                            name=model_name,
                            version=version_info.version,
                            model_type=MODEL_CONFIG[model_name]["type"],
                            created_at=datetime.fromtimestamp(run.info.start_time / 1000),
                            performance_metrics=dict(run.data.metrics),
                            features=MODEL_CONFIG[model_name]["features"],
                            mlflow_run_id=version_info.run_id
                        )
                        
                        self.models[model_name] = model
                        self.metadata[model_name] = metadata
                        
                        logger.info(
                            "Loaded model from MLflow",
                            model_name=model_name,
                            version=version_info.version,
                            stage=version_info.current_stage
                        )
                        
                except Exception as e:
                    logger.warning(
                        "Failed to load model from MLflow",
                        model_name=model_name,
                        error=str(e)
                    )
                    continue
                    
        except Exception as e:
            logger.error("MLflow connection failed", error=str(e))
            raise
    
    async def _load_local_models(self) -> None:
        """Load models from local storage as fallback"""
        for model_file in self.storage_path.glob("*.pkl"):
            try:
                model_name = model_file.stem
                
                # Skip if already loaded from MLflow
                if model_name in self.models:
                    continue
                
                with open(model_file, 'rb') as f:
                    model_data = pickle.load(f)
                
                # Load metadata if exists
                metadata_file = self.storage_path / f"{model_name}_metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata_dict = json.load(f)
                    
                    metadata = ModelMetadata(
                        name=metadata_dict["name"],
                        version=metadata_dict["version"],
                        model_type=metadata_dict["model_type"],
                        created_at=datetime.fromisoformat(metadata_dict["created_at"]),
                        performance_metrics=metadata_dict["performance_metrics"],
                        features=metadata_dict["features"],
                        model_path=str(model_file)
                    )
                else:
                    # Create basic metadata for legacy models
                    metadata = ModelMetadata(
                        name=model_name,
                        version="1.0.0",
                        model_type="unknown",
                        created_at=datetime.fromtimestamp(model_file.stat().st_mtime),
                        performance_metrics={},
                        features=[],
                        model_path=str(model_file)
                    )
                
                self.models[model_name] = model_data
                self.metadata[model_name] = metadata
                
                logger.info("Loaded local model", model_name=model_name)
                
            except Exception as e:
                logger.warning(
                    "Failed to load local model",
                    model_file=str(model_file),
                    error=str(e)
                )
                continue
    
    async def get_model(self, model_name: str) -> Optional[Any]:
        """Get model by name with caching"""
        if model_name not in self.models:
            logger.warning("Model not found", model_name=model_name)
            return None
        
        # Update usage stats
        if model_name in self.metadata:
            self.metadata[model_name].last_used = datetime.utcnow()
            self.metadata[model_name].prediction_count += 1
        
        return self.models[model_name]
    
    async def register_model(self, 
                           model_name: str,
                           model: Any,
                           metadata: ModelMetadata,
                           save_local: bool = True) -> bool:
        """Register a new model"""
        try:
            # Validate model performance
            if not await self._validate_model_performance(model_name, metadata):
                logger.error(
                    "Model performance below threshold",
                    model_name=model_name,
                    metrics=metadata.performance_metrics
                )
                return False
            
            # Save model locally
            if save_local:
                model_path = self.storage_path / f"{model_name}.pkl"
                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)
                
                metadata_path = self.storage_path / f"{model_name}_metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata.to_dict(), f, indent=2)
                
                metadata.model_path = str(model_path)
            
            # Store in memory
            self.models[model_name] = model
            self.metadata[model_name] = metadata
            
            # Cache in Redis if available
            if self.redis_client:
                cache_key = f"model_metadata:{model_name}"
                await self.redis_client.setex(
                    cache_key,
                    self.model_cache_ttl,
                    json.dumps(metadata.to_dict())
                )
            
            logger.info(
                "Model registered successfully",
                model_name=model_name,
                version=metadata.version,
                performance=metadata.performance_metrics
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to register model",
                model_name=model_name,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def _validate_model_performance(self, 
                                        model_name: str, 
                                        metadata: ModelMetadata) -> bool:
        """Validate model meets performance thresholds"""
        if model_name not in self.performance_thresholds:
            return True  # No thresholds defined
        
        thresholds = self.performance_thresholds[model_name]
        metrics = metadata.performance_metrics
        
        for metric_name, threshold in thresholds.items():
            if metric_name not in metrics:
                logger.warning(
                    "Required metric missing",
                    model_name=model_name,
                    metric=metric_name
                )
                return False
            
            metric_value = metrics[metric_name]
            
            # Handle different metric types
            if metric_name.startswith('min_'):
                if metric_value < threshold:
                    return False
            elif metric_name.startswith('max_'):
                if metric_value > threshold:
                    return False
        
        return True
    
    async def get_model_metadata(self, model_name: str) -> Optional[ModelMetadata]:
        """Get model metadata"""
        return self.metadata.get(model_name)
    
    async def list_models(self) -> Dict[str, Dict[str, Any]]:
        """List all available models with metadata"""
        models_info = {}
        
        for model_name, metadata in self.metadata.items():
            models_info[model_name] = {
                "metadata": metadata.to_dict(),
                "is_loaded": model_name in self.models,
                "health_status": await self._check_model_health(model_name)
            }
        
        return models_info
    
    async def _check_model_health(self, model_name: str) -> str:
        """Check model health status"""
        try:
            if model_name not in self.models:
                return "not_loaded"
            
            # Check if model was used recently
            metadata = self.metadata.get(model_name)
            if metadata:
                time_since_use = datetime.utcnow() - metadata.last_used
                if time_since_use > timedelta(days=7):
                    return "stale"
            
            # Basic health check - try a dummy prediction
            model = self.models[model_name]
            if hasattr(model, 'predict'):
                # Create dummy input based on features
                features = metadata.features if metadata else []
                if features:
                    dummy_input = np.zeros((1, len(features)))
                    try:
                        _ = model.predict(dummy_input)
                        return "healthy"
                    except Exception:
                        return "unhealthy"
            
            return "unknown"
            
        except Exception as e:
            logger.error(
                "Health check failed",
                model_name=model_name,
                error=str(e)
            )
            return "unhealthy"
    
    async def get_health_status(self) -> Dict[str, str]:
        """Get health status of all models"""
        health_status = {}
        
        for model_name in self.models:
            health_status[model_name] = await self._check_model_health(model_name)
        
        return health_status
    
    async def get_loaded_model_count(self) -> int:
        """Get number of loaded models"""
        return len(self.models)
    
    async def unload_model(self, model_name: str) -> bool:
        """Unload model from memory"""
        try:
            if model_name in self.models:
                del self.models[model_name]
                logger.info("Model unloaded", model_name=model_name)
                return True
            return False
        except Exception as e:
            logger.error("Failed to unload model", model_name=model_name, error=str(e))
            return False
    
    async def reload_model(self, model_name: str) -> bool:
        """Reload specific model"""
        try:
            # Unload first
            await self.unload_model(model_name)
            
            # Reload from MLflow or local
            await self._load_from_mlflow()
            if model_name not in self.models:
                await self._load_local_models()
            
            return model_name in self.models
            
        except Exception as e:
            logger.error("Failed to reload model", model_name=model_name, error=str(e))
            return False
    
    async def get_model_performance_metrics(self, model_name: str) -> Dict[str, float]:
        """Get model performance metrics"""
        metadata = self.metadata.get(model_name)
        if metadata:
            return metadata.performance_metrics
        return {}
    
    async def update_model_metrics(self, 
                                 model_name: str, 
                                 new_metrics: Dict[str, float]) -> bool:
        """Update model performance metrics"""
        try:
            if model_name in self.metadata:
                self.metadata[model_name].performance_metrics.update(new_metrics)
                
                # Update in Redis cache
                if self.redis_client:
                    cache_key = f"model_metadata:{model_name}"
                    await self.redis_client.setex(
                        cache_key,
                        self.model_cache_ttl,
                        json.dumps(self.metadata[model_name].to_dict())
                    )
                
                logger.info(
                    "Model metrics updated",
                    model_name=model_name,
                    new_metrics=new_metrics
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(
                "Failed to update model metrics",
                model_name=model_name,
                error=str(e)
            )
            return False