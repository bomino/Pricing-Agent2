"""
Prediction endpoints for the ML service
"""
import asyncio
import uuid
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.security import HTTPBearer
import structlog

from ...models.schemas import (
    PricePredictionRequest,
    PricePredictionResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    PredictionStatus,
    ErrorResponse,
)
from ...services.ml_service import MLService
from ...services.model_registry import ModelRegistry
from ...dependencies import (
    get_ml_service,
    get_current_user,
    verify_service_key,
    rate_limit,
    get_redis,
)

logger = structlog.get_logger()
router = APIRouter()
security = HTTPBearer()


@router.post(
    "/price",
    response_model=PricePredictionResponse,
    summary="Predict material price",
    description="Generate price prediction for a single material",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    }
)
async def predict_price(
    request: PricePredictionRequest,
    background_tasks: BackgroundTasks,
    ml_service: MLService = Depends(get_ml_service),
    user=Depends(get_current_user),
    _=Depends(rate_limit("ml_predict")),
):
    """
    Predict price for a single material based on specifications and context.
    
    This endpoint uses machine learning models to predict the price of a material
    based on historical data, market trends, and contextual factors.
    """
    try:
        logger.info(
            "Price prediction request",
            material_id=request.material_id,
            quantity=str(request.quantity),
            user_id=str(user.id) if user else None,
        )
        
        # Prepare prediction items
        items = [{
            'item_id': request.material_id,
            'material_id': request.material_id,
            'quantity': float(request.quantity),
            'supplier_id': request.supplier_id,
            'delivery_date': request.delivery_date,
            'region': request.region,
            'payment_terms': request.payment_terms,
            'specifications': request.specifications or {},
            'context': request.context or {},
            'category': request.specifications.get('category', 'general') if request.specifications else 'general'
        }]
        
        # Generate prediction
        prediction_results = await ml_service.predict_prices(items, include_uncertainty=True)
        prediction_result = prediction_results[0] if prediction_results else None
        
        if not prediction_result:
            raise HTTPException(status_code=503, detail="Prediction service unavailable")
        
        # Create response
        confidence_interval = prediction_result.get("confidence_interval", {})
        predicted_price = prediction_result.get("predicted_price", 0)
        unit_price = predicted_price / float(request.quantity) if request.quantity > 0 else 0
        
        response = PricePredictionResponse(
            material_id=request.material_id,
            quantity=request.quantity,
            predicted_price=predicted_price,
            unit_price=unit_price,
            currency="USD",
            confidence_score=0.85,  # Default confidence
            prediction_interval={
                "lower": confidence_interval.get("lower", predicted_price * 0.9),
                "upper": confidence_interval.get("upper", predicted_price * 1.1)
            },
            model_version=prediction_result.get("model_version", "1.0"),
            features_used=[],
            similar_quotes=[],
            recommendations=[],
            metadata={"prediction_timestamp": prediction_result.get("prediction_timestamp")},
            created_at=datetime.utcnow(),
        )
        
        # Log successful prediction
        background_tasks.add_task(
            log_prediction,
            user_id=str(user.id) if user else None,
            request_data=request.dict(),
            response_data=response.dict(),
            success=True,
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error in price prediction: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except TimeoutError as e:
        logger.error(f"Timeout in price prediction: {e}")
        raise HTTPException(status_code=503, detail="Prediction service timeout")
    
    except Exception as e:
        logger.error(f"Error in price prediction: {e}", exc_info=True)
        
        # Log failed prediction
        background_tasks.add_task(
            log_prediction,
            user_id=str(user.id) if user else None,
            request_data=request.dict(),
            response_data=None,
            success=False,
            error=str(e),
        )
        
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/batch",
    response_model=BatchPredictionResponse,
    summary="Batch price predictions",
    description="Generate price predictions for multiple materials",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    }
)
async def predict_price_batch(
    request: BatchPredictionRequest,
    background_tasks: BackgroundTasks,
    ml_service: MLService = Depends(get_ml_service),
    user=Depends(get_current_user),
    redis=Depends(get_redis),
    _=Depends(rate_limit("bulk_operations")),
):
    """
    Generate price predictions for multiple materials in batch.
    
    Supports both synchronous and asynchronous processing modes.
    For large batches, use async_processing=True to avoid timeouts.
    """
    try:
        batch_id = str(uuid.uuid4())
        
        logger.info(
            "Batch prediction request",
            batch_id=batch_id,
            prediction_count=len(request.predictions),
            async_processing=request.async_processing,
            user_id=str(user.id) if user else None,
        )
        
        # Create initial batch response
        batch_response = BatchPredictionResponse(
            batch_id=batch_id,
            status=PredictionStatus.PENDING,
            total_predictions=len(request.predictions),
            completed_predictions=0,
            failed_predictions=0,
            created_at=datetime.utcnow(),
        )
        
        if request.async_processing:
            # Store batch request in Redis for async processing
            await redis.setex(
                f"batch:{batch_id}",
                3600,  # 1 hour TTL
                batch_response.json()
            )
            
            # Process asynchronously
            background_tasks.add_task(
                process_batch_async,
                batch_id=batch_id,
                predictions=request.predictions,
                ml_service=ml_service,
                callback_url=request.callback_url,
                user_id=str(user.id) if user else None,
            )
            
            batch_response.status = PredictionStatus.IN_PROGRESS
            return batch_response
        
        else:
            # Process synchronously
            return await process_batch_sync(
                batch_id=batch_id,
                predictions=request.predictions,
                ml_service=ml_service,
                user_id=str(user.id) if user else None,
            )
            
    except Exception as e:
        logger.error(f"Error in batch prediction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/batch/{batch_id}",
    response_model=BatchPredictionResponse,
    summary="Get batch prediction status",
    description="Get the status and results of a batch prediction",
)
async def get_batch_prediction(
    batch_id: str,
    user=Depends(get_current_user),
    redis=Depends(get_redis),
):
    """
    Get the status and results of a batch prediction by batch ID.
    """
    try:
        # Get batch status from Redis
        batch_data = await redis.get(f"batch:{batch_id}")
        
        if not batch_data:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        batch_response = BatchPredictionResponse.parse_raw(batch_data)
        
        logger.info(
            "Batch status request",
            batch_id=batch_id,
            status=batch_response.status,
            user_id=str(user.id) if user else None,
        )
        
        return batch_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch prediction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/batch/{batch_id}",
    summary="Cancel batch prediction",
    description="Cancel a running batch prediction",
)
async def cancel_batch_prediction(
    batch_id: str,
    user=Depends(get_current_user),
    redis=Depends(get_redis),
):
    """
    Cancel a running batch prediction.
    """
    try:
        # Get batch status from Redis
        batch_data = await redis.get(f"batch:{batch_id}")
        
        if not batch_data:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        batch_response = BatchPredictionResponse.parse_raw(batch_data)
        
        if batch_response.status in [PredictionStatus.COMPLETED, PredictionStatus.FAILED]:
            raise HTTPException(status_code=400, detail="Batch already completed")
        
        # Mark as cancelled (we'll handle this in the async processor)
        batch_response.status = PredictionStatus.FAILED
        batch_response.completed_at = datetime.utcnow()
        
        await redis.setex(
            f"batch:{batch_id}",
            3600,
            batch_response.json()
        )
        
        logger.info(
            "Batch prediction cancelled",
            batch_id=batch_id,
            user_id=str(user.id) if user else None,
        )
        
        return {"message": "Batch prediction cancelled"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling batch prediction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# Background task functions
async def process_batch_sync(
    batch_id: str,
    predictions: List[PricePredictionRequest],
    ml_service: MLService,
    user_id: str = None,
) -> BatchPredictionResponse:
    """Process batch predictions synchronously"""
    
    batch_response = BatchPredictionResponse(
        batch_id=batch_id,
        status=PredictionStatus.IN_PROGRESS,
        total_predictions=len(predictions),
        completed_predictions=0,
        failed_predictions=0,
        created_at=datetime.utcnow(),
    )
    
    start_time = datetime.utcnow()
    
    # Process predictions concurrently with semaphore to limit concurrency
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent predictions
    
    async def process_single_prediction(pred_request):
        async with semaphore:
            try:
                result = await ml_service.predict_price(
                    material_id=pred_request.material_id,
                    quantity=float(pred_request.quantity),
                    supplier_id=pred_request.supplier_id,
                    delivery_date=pred_request.delivery_date,
                    region=pred_request.region,
                    payment_terms=pred_request.payment_terms,
                    specifications=pred_request.specifications,
                    context=pred_request.context,
                )
                
                return PricePredictionResponse(
                    material_id=pred_request.material_id,
                    quantity=pred_request.quantity,
                    predicted_price=result["predicted_price"],
                    unit_price=result["unit_price"],
                    currency=result.get("currency", "USD"),
                    confidence_score=result["confidence_score"],
                    prediction_interval=result["prediction_interval"],
                    model_version=result["model_version"],
                    features_used=result["features_used"],
                    similar_quotes=result.get("similar_quotes", []),
                    recommendations=result.get("recommendations", []),
                    metadata=result.get("metadata", {}),
                    created_at=datetime.utcnow(),
                )
                
            except Exception as e:
                logger.error(f"Error processing prediction: {e}")
                return {
                    "error": str(e),
                    "material_id": pred_request.material_id,
                }
    
    # Execute all predictions
    results = await asyncio.gather(
        *[process_single_prediction(pred) for pred in predictions],
        return_exceptions=True
    )
    
    # Separate successful results from errors
    for result in results:
        if isinstance(result, dict) and "error" in result:
            batch_response.errors.append(result)
            batch_response.failed_predictions += 1
        elif isinstance(result, PricePredictionResponse):
            batch_response.results.append(result)
            batch_response.completed_predictions += 1
        else:
            batch_response.errors.append({
                "error": "Unknown error",
                "result": str(result),
            })
            batch_response.failed_predictions += 1
    
    # Finalize batch response
    batch_response.status = PredictionStatus.COMPLETED
    batch_response.completed_at = datetime.utcnow()
    batch_response.processing_time_seconds = (
        batch_response.completed_at - start_time
    ).total_seconds()
    
    return batch_response


async def process_batch_async(
    batch_id: str,
    predictions: List[PricePredictionRequest],
    ml_service: MLService,
    callback_url: str = None,
    user_id: str = None,
):
    """Process batch predictions asynchronously"""
    
    try:
        logger.info(f"Starting async batch processing for {batch_id}")
        
        # Process synchronously but in background
        batch_response = await process_batch_sync(
            batch_id=batch_id,
            predictions=predictions,
            ml_service=ml_service,
            user_id=user_id,
        )
        
        # Store final results
        redis_client = await get_redis()
        await redis_client.setex(
            f"batch:{batch_id}",
            3600,
            batch_response.json()
        )
        
        # Send callback if provided
        if callback_url:
            await send_callback(callback_url, batch_response)
        
        logger.info(
            "Async batch processing completed",
            batch_id=batch_id,
            completed=batch_response.completed_predictions,
            failed=batch_response.failed_predictions,
        )
        
    except Exception as e:
        logger.error(f"Error in async batch processing: {e}", exc_info=True)
        
        # Mark batch as failed
        batch_response = BatchPredictionResponse(
            batch_id=batch_id,
            status=PredictionStatus.FAILED,
            total_predictions=len(predictions),
            completed_predictions=0,
            failed_predictions=len(predictions),
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            errors=[{"error": str(e)}]
        )
        
        redis_client = await get_redis()
        await redis_client.setex(
            f"batch:{batch_id}",
            3600,
            batch_response.json()
        )


async def send_callback(callback_url: str, batch_response: BatchPredictionResponse):
    """Send callback notification"""
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                callback_url,
                json=batch_response.dict(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
        logger.info(f"Callback sent successfully to {callback_url}")
        
    except Exception as e:
        logger.error(f"Failed to send callback to {callback_url}: {e}")


async def log_prediction(
    user_id: str = None,
    request_data: dict = None,
    response_data: dict = None,
    success: bool = True,
    error: str = None,
):
    """Log prediction for audit and monitoring"""
    try:
        # This would typically log to database or monitoring system
        logger.info(
            "Prediction logged",
            user_id=user_id,
            material_id=request_data.get("material_id") if request_data else None,
            success=success,
            error=error,
        )
    except Exception as e:
        logger.error(f"Failed to log prediction: {e}")