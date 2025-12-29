"""
Model Management API Endpoints
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import structlog

from ...dependencies import (
    get_model_registry,
    get_ml_service,
    require_staff,
    rate_limit
)
from ...services.model_registry import ModelRegistry
from ...services.training_pipeline import AutoMLTrainer
from ...services.monitoring import ModelMonitor
from ...models.schemas import (
    ModelInfo,
    ModelTrainingRequest,
    ModelTrainingResponse,
    ModelHealthReport,
    ErrorResponse
)

logger = structlog.get_logger()
router = APIRouter()


@router.get(
    "/",
    response_model=Dict[str, ModelInfo],
    summary="List all models",
    description="Get information about all available ML models"
)
async def list_models(
    model_registry: ModelRegistry = Depends(get_model_registry),
    user=Depends(require_staff)
):
    """List all available models with their metadata"""
    try:
        models_info = await model_registry.list_models()
        
        # Convert to response format
        response = {}
        for model_name, model_data in models_info.items():
            metadata = model_data['metadata']
            response[model_name] = ModelInfo(
                name=metadata['name'],
                version=metadata['version'],
                model_type=metadata['model_type'],
                created_at=datetime.fromisoformat(metadata['created_at']),
                performance_metrics=metadata['performance_metrics'],
                features=metadata['features'],
                is_loaded=model_data['is_loaded'],
                health_status=model_data['health_status'],
                last_used=datetime.fromisoformat(metadata['last_used']),
                prediction_count=metadata['prediction_count']
            )
        
        logger.info(f"Listed {len(response)} models", user_id=user.id)
        return response
        
    except Exception as e:
        logger.error(f"Failed to list models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve model information")


@router.get(
    "/{model_name}",
    response_model=ModelInfo,
    summary="Get model information",
    description="Get detailed information about a specific model"
)
async def get_model_info(
    model_name: str,
    model_registry: ModelRegistry = Depends(get_model_registry),
    user=Depends(require_staff)
):
    """Get information about a specific model"""
    try:
        metadata = await model_registry.get_model_metadata(model_name)
        
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
        
        # Check if model is loaded
        model = await model_registry.get_model(model_name)
        is_loaded = model is not None
        
        # Get health status
        health_status = await model_registry._check_model_health(model_name)
        
        model_info = ModelInfo(
            name=metadata.name,
            version=metadata.version,
            model_type=metadata.model_type,
            created_at=metadata.created_at,
            performance_metrics=metadata.performance_metrics,
            features=metadata.features,
            is_loaded=is_loaded,
            health_status=health_status,
            last_used=metadata.last_used,
            prediction_count=metadata.prediction_count
        )
        
        logger.info(f"Retrieved model info", model_name=model_name, user_id=user.id)
        return model_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve model information")


@router.post(
    "/{model_name}/reload",
    summary="Reload model",
    description="Reload a model from storage"
)
async def reload_model(
    model_name: str,
    background_tasks: BackgroundTasks,
    model_registry: ModelRegistry = Depends(get_model_registry),
    user=Depends(require_staff)
):
    """Reload a model from storage"""
    try:
        success = await model_registry.reload_model(model_name)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Failed to reload model {model_name}")
        
        # Log reload action
        background_tasks.add_task(
            log_model_action,
            action="reload",
            model_name=model_name,
            user_id=user.id,
            success=True
        )
        
        logger.info(f"Model reloaded", model_name=model_name, user_id=user.id)
        return {"message": f"Model {model_name} reloaded successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        background_tasks.add_task(
            log_model_action,
            action="reload",
            model_name=model_name,
            user_id=user.id,
            success=False,
            error=str(e)
        )
        logger.error(f"Failed to reload model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to reload model")


@router.delete(
    "/{model_name}",
    summary="Unload model",
    description="Unload a model from memory"
)
async def unload_model(
    model_name: str,
    background_tasks: BackgroundTasks,
    model_registry: ModelRegistry = Depends(get_model_registry),
    user=Depends(require_staff)
):
    """Unload a model from memory"""
    try:
        success = await model_registry.unload_model(model_name)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Model {model_name} not found or already unloaded")
        
        # Log unload action
        background_tasks.add_task(
            log_model_action,
            action="unload",
            model_name=model_name,
            user_id=user.id,
            success=True
        )
        
        logger.info(f"Model unloaded", model_name=model_name, user_id=user.id)
        return {"message": f"Model {model_name} unloaded successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        background_tasks.add_task(
            log_model_action,
            action="unload",
            model_name=model_name,
            user_id=user.id,
            success=False,
            error=str(e)
        )
        logger.error(f"Failed to unload model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to unload model")


@router.post(
    "/train",
    response_model=ModelTrainingResponse,
    summary="Train new model",
    description="Start training a new model"
)
async def train_model(
    request: ModelTrainingRequest,
    background_tasks: BackgroundTasks,
    model_registry: ModelRegistry = Depends(get_model_registry),
    user=Depends(require_staff),
    _=Depends(rate_limit("model_operations"))
):
    """Start training a new model"""
    try:
        # Initialize AutoML trainer
        automl_trainer = AutoMLTrainer(model_registry)
        
        if request.model_type not in ['price_predictor', 'anomaly_detector', 'demand_forecaster']:
            raise HTTPException(status_code=400, detail=f"Unsupported model type: {request.model_type}")
        
        # Start training in background
        background_tasks.add_task(
            train_model_background,
            automl_trainer=automl_trainer,
            model_type=request.model_type,
            user_id=user.id,
            training_config=request.config
        )
        
        training_response = ModelTrainingResponse(
            model_type=request.model_type,
            status="started",
            started_at=datetime.utcnow(),
            message=f"Training started for {request.model_type}",
            training_id=f"{request.model_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        )
        
        logger.info(
            f"Model training started",
            model_type=request.model_type,
            user_id=user.id,
            training_id=training_response.training_id
        )
        
        return training_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start model training: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start model training")


@router.get(
    "/{model_name}/health",
    response_model=ModelHealthReport,
    summary="Get model health",
    description="Get comprehensive health report for a model"
)
async def get_model_health(
    model_name: str,
    model_registry: ModelRegistry = Depends(get_model_registry),
    ml_service=Depends(get_ml_service),
    user=Depends(require_staff)
):
    """Get comprehensive health report for a model"""
    try:
        # Initialize model monitor
        from ...dependencies import get_redis
        redis_client = await get_redis()
        model_monitor = ModelMonitor(model_registry, redis_client)
        
        # Run health check
        health_report = await model_monitor.monitor_model_health(model_name)
        
        # Convert to response format
        health_response = ModelHealthReport(
            model_name=model_name,
            overall_health=health_report['overall_health'],
            health_score=health_report['health_score'],
            checks=health_report['checks'],
            alerts=[
                {
                    'level': alert['level'],
                    'message': alert['message'],
                    'recommendation': alert['recommendation']
                }
                for alert in health_report['alerts']
            ],
            monitored_at=datetime.fromisoformat(health_report['monitored_at'])
        )
        
        logger.info(f"Model health check completed", model_name=model_name, user_id=user.id)
        return health_response
        
    except Exception as e:
        logger.error(f"Failed to get model health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve model health information")


@router.get(
    "/{model_name}/metrics",
    summary="Get model metrics",
    description="Get performance metrics for a model"
)
async def get_model_metrics(
    model_name: str,
    model_registry: ModelRegistry = Depends(get_model_registry),
    user=Depends(require_staff)
):
    """Get performance metrics for a model"""
    try:
        metrics = await model_registry.get_model_performance_metrics(model_name)
        
        if not metrics:
            raise HTTPException(status_code=404, detail=f"No metrics found for model {model_name}")
        
        logger.info(f"Retrieved model metrics", model_name=model_name, user_id=user.id)
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve model metrics")


# Background tasks
async def train_model_background(
    automl_trainer: AutoMLTrainer,
    model_type: str,
    user_id: str,
    training_config: Dict[str, Any]
):
    """Background task for model training"""
    try:
        logger.info(f"Starting background training for {model_type}")
        
        # Run training pipeline
        results = await automl_trainer.run_training_pipeline([model_type])
        
        logger.info(
            f"Background training completed",
            model_type=model_type,
            user_id=user_id,
            results=results
        )
        
    except Exception as e:
        logger.error(f"Background training failed: {e}", exc_info=True)


async def log_model_action(
    action: str,
    model_name: str,
    user_id: str,
    success: bool = True,
    error: Optional[str] = None
):
    """Log model management actions"""
    try:
        log_entry = {
            'action': action,
            'model_name': model_name,
            'user_id': user_id,
            'success': success,
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # In production, this would log to a database or monitoring system
        logger.info("Model action logged", **log_entry)
        
    except Exception as e:
        logger.error(f"Failed to log model action: {e}")