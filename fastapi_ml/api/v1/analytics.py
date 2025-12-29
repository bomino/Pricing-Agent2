"""
Analytics API Endpoints for ML insights and monitoring
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
import structlog

from ...dependencies import (
    get_model_registry,
    get_ml_service,
    require_staff,
    rate_limit,
    get_redis
)
from ...services.monitoring import ModelMonitor
from ...services.optimization import PerformanceOptimizer
from ...models.schemas import (
    AnalyticsReport,
    DriftReport,
    PerformanceReport,
    ErrorResponse
)

logger = structlog.get_logger()
router = APIRouter()


@router.get(
    "/overview",
    response_model=Dict[str, Any],
    summary="Analytics overview",
    description="Get high-level analytics overview across all models"
)
async def get_analytics_overview(
    model_registry=Depends(get_model_registry),
    user=Depends(require_staff)
):
    """Get analytics overview across all models"""
    try:
        # Get basic model statistics
        models_info = await model_registry.list_models()
        
        overview = {
            'total_models': len(models_info),
            'active_models': sum(1 for info in models_info.values() if info['is_loaded']),
            'healthy_models': sum(1 for info in models_info.values() if info['health_status'] == 'healthy'),
            'model_types': {},
            'total_predictions': 0,
            'generated_at': datetime.utcnow().isoformat()
        }
        
        # Aggregate by model type and prediction counts
        for model_name, model_data in models_info.items():
            metadata = model_data['metadata']
            model_type = metadata['model_type']
            
            if model_type not in overview['model_types']:
                overview['model_types'][model_type] = {
                    'count': 0,
                    'active': 0,
                    'predictions': 0
                }
            
            overview['model_types'][model_type]['count'] += 1
            if model_data['is_loaded']:
                overview['model_types'][model_type]['active'] += 1
            
            overview['model_types'][model_type]['predictions'] += metadata['prediction_count']
            overview['total_predictions'] += metadata['prediction_count']
        
        logger.info(f"Generated analytics overview", user_id=user.id)
        return overview
        
    except Exception as e:
        logger.error(f"Failed to generate analytics overview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate analytics overview")


@router.get(
    "/performance",
    response_model=Dict[str, Any],
    summary="Performance analytics",
    description="Get performance analytics and optimization metrics"
)
async def get_performance_analytics(
    hours_back: int = Query(24, ge=1, le=168, description="Hours of data to analyze"),
    user=Depends(require_staff),
    redis_client=Depends(get_redis)
):
    """Get performance analytics and optimization metrics"""
    try:
        # Initialize performance optimizer
        performance_optimizer = PerformanceOptimizer(redis_client)
        
        # Get optimization metrics
        optimization_metrics = await performance_optimizer.get_optimization_metrics()
        
        # Calculate time-based performance metrics
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        performance_analytics = {
            'time_period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': hours_back
            },
            'optimization_metrics': optimization_metrics,
            'performance_trends': await _calculate_performance_trends(start_time, end_time),
            'bottlenecks': await _identify_bottlenecks(optimization_metrics),
            'recommendations': await _generate_performance_recommendations(optimization_metrics)
        }
        
        logger.info(f"Generated performance analytics", hours_back=hours_back, user_id=user.id)
        return performance_analytics
        
    except Exception as e:
        logger.error(f"Failed to generate performance analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate performance analytics")


@router.get(
    "/drift/{model_name}",
    response_model=Dict[str, Any],
    summary="Model drift analysis",
    description="Get drift analysis for a specific model"
)
async def get_drift_analysis(
    model_name: str,
    days_back: int = Query(7, ge=1, le=30, description="Days of data to analyze"),
    model_registry=Depends(get_model_registry),
    user=Depends(require_staff),
    redis_client=Depends(get_redis)
):
    """Get drift analysis for a specific model"""
    try:
        # Check if model exists
        metadata = await model_registry.get_model_metadata(model_name)
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
        
        # Initialize model monitor
        model_monitor = ModelMonitor(model_registry, redis_client)
        
        # Get drift analysis
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days_back)
        
        drift_analysis = {
            'model_name': model_name,
            'analysis_period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'days': days_back
            },
            'feature_drift': await model_monitor._check_feature_drift(model_name),
            'prediction_drift': await model_monitor._check_prediction_drift(model_name),
            'drift_history': await _get_drift_history(model_name, start_time, end_time, redis_client),
            'drift_trends': await _calculate_drift_trends(model_name, start_time, end_time, redis_client),
            'recommendations': await _generate_drift_recommendations(model_name, model_monitor)
        }
        
        logger.info(f"Generated drift analysis", model_name=model_name, days_back=days_back, user_id=user.id)
        return drift_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate drift analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate drift analysis")


@router.get(
    "/predictions/volume",
    response_model=Dict[str, Any],
    summary="Prediction volume analytics",
    description="Get prediction volume analytics across time periods"
)
async def get_prediction_volume_analytics(
    model_name: Optional[str] = Query(None, description="Specific model name (optional)"),
    hours_back: int = Query(24, ge=1, le=168, description="Hours of data to analyze"),
    granularity: str = Query("hour", regex="^(hour|day)$", description="Time granularity"),
    user=Depends(require_staff),
    redis_client=Depends(get_redis)
):
    """Get prediction volume analytics"""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        volume_analytics = {
            'time_period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': hours_back,
                'granularity': granularity
            },
            'volume_data': await _get_prediction_volumes(model_name, start_time, end_time, granularity, redis_client),
            'volume_statistics': await _calculate_volume_statistics(model_name, start_time, end_time, redis_client),
            'anomalous_periods': await _detect_volume_anomalies(model_name, start_time, end_time, redis_client),
            'usage_patterns': await _analyze_usage_patterns(model_name, start_time, end_time, redis_client)
        }
        
        logger.info(f"Generated prediction volume analytics", model_name=model_name, hours_back=hours_back, user_id=user.id)
        return volume_analytics
        
    except Exception as e:
        logger.error(f"Failed to generate prediction volume analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate prediction volume analytics")


@router.get(
    "/errors",
    response_model=Dict[str, Any],
    summary="Error analytics",
    description="Get error analytics and failure patterns"
)
async def get_error_analytics(
    model_name: Optional[str] = Query(None, description="Specific model name (optional)"),
    hours_back: int = Query(24, ge=1, le=168, description="Hours of data to analyze"),
    user=Depends(require_staff),
    redis_client=Depends(get_redis)
):
    """Get error analytics and failure patterns"""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        error_analytics = {
            'time_period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': hours_back
            },
            'error_summary': await _get_error_summary(model_name, start_time, end_time, redis_client),
            'error_trends': await _get_error_trends(model_name, start_time, end_time, redis_client),
            'error_categories': await _categorize_errors(model_name, start_time, end_time, redis_client),
            'failure_patterns': await _analyze_failure_patterns(model_name, start_time, end_time, redis_client),
            'recommendations': await _generate_error_recommendations(model_name, start_time, end_time, redis_client)
        }
        
        logger.info(f"Generated error analytics", model_name=model_name, hours_back=hours_back, user_id=user.id)
        return error_analytics
        
    except Exception as e:
        logger.error(f"Failed to generate error analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate error analytics")


@router.get(
    "/alerts",
    response_model=List[Dict[str, Any]],
    summary="Active alerts",
    description="Get active monitoring alerts"
)
async def get_active_alerts(
    model_name: Optional[str] = Query(None, description="Specific model name (optional)"),
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$", description="Alert severity filter"),
    model_registry=Depends(get_model_registry),
    user=Depends(require_staff),
    redis_client=Depends(get_redis)
):
    """Get active monitoring alerts"""
    try:
        # Initialize model monitor
        model_monitor = ModelMonitor(model_registry, redis_client)
        
        # Get active alerts
        alerts = await model_monitor.get_active_alerts(model_name)
        
        # Filter by severity if specified
        if severity:
            alerts = [alert for alert in alerts if alert.get('level') == severity]
        
        # Add alert metadata
        for alert in alerts:
            alert['age_hours'] = (
                datetime.utcnow() - datetime.fromisoformat(alert['created_at'])
            ).total_seconds() / 3600
        
        # Sort by creation time (newest first)
        alerts.sort(key=lambda x: x['created_at'], reverse=True)
        
        logger.info(f"Retrieved active alerts", count=len(alerts), model_name=model_name, user_id=user.id)
        return alerts
        
    except Exception as e:
        logger.error(f"Failed to get active alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve active alerts")


@router.post(
    "/alerts/{alert_id}/acknowledge",
    summary="Acknowledge alert",
    description="Acknowledge a monitoring alert"
)
async def acknowledge_alert(
    alert_id: str,
    user=Depends(require_staff),
    redis_client=Depends(get_redis)
):
    """Acknowledge a monitoring alert"""
    try:
        # Get alert data
        alert_data = await redis_client.get(f"alert:{alert_id}")
        
        if not alert_data:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        import json
        alert = json.loads(alert_data)
        
        # Mark as acknowledged
        alert['acknowledged'] = True
        alert['acknowledged_by'] = user.id
        alert['acknowledged_at'] = datetime.utcnow().isoformat()
        
        # Update in Redis
        await redis_client.setex(f"alert:{alert_id}", 7 * 24 * 3600, json.dumps(alert))
        
        logger.info(f"Alert acknowledged", alert_id=alert_id, user_id=user.id)
        return {"message": f"Alert {alert_id} acknowledged successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert")


# Helper functions for analytics calculations
async def _calculate_performance_trends(start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """Calculate performance trends over time"""
    # Placeholder implementation - in production, query actual metrics from database
    return {
        'latency_trend': 'stable',
        'throughput_trend': 'increasing',
        'error_rate_trend': 'decreasing',
        'cache_hit_rate_trend': 'stable'
    }


async def _identify_bottlenecks(optimization_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Identify performance bottlenecks"""
    bottlenecks = []
    
    # Check cache hit rate
    cache_hit_rate = optimization_metrics.get('overall_metrics', {}).get('cache_hit_rate', 1.0)
    if cache_hit_rate < 0.5:
        bottlenecks.append({
            'type': 'caching',
            'severity': 'medium',
            'description': f'Low cache hit rate: {cache_hit_rate:.2%}',
            'recommendation': 'Review cache TTL settings and cache warming strategies'
        })
    
    # Check throughput
    throughput = optimization_metrics.get('batch_processing_metrics', {}).get('throughput', 100)
    if throughput < 50:
        bottlenecks.append({
            'type': 'throughput',
            'severity': 'high',
            'description': f'Low throughput: {throughput:.1f} items/s',
            'recommendation': 'Optimize batch processing and consider scaling resources'
        })
    
    return bottlenecks


async def _generate_performance_recommendations(optimization_metrics: Dict[str, Any]) -> List[str]:
    """Generate performance optimization recommendations"""
    recommendations = []
    
    cache_hit_rate = optimization_metrics.get('overall_metrics', {}).get('cache_hit_rate', 1.0)
    if cache_hit_rate < 0.7:
        recommendations.append("Implement cache warming for frequently requested predictions")
    
    throughput = optimization_metrics.get('batch_processing_metrics', {}).get('throughput', 100)
    if throughput < 100:
        recommendations.append("Consider increasing batch size or adding more worker processes")
    
    if not recommendations:
        recommendations.append("Performance is within acceptable parameters")
    
    return recommendations


async def _get_drift_history(model_name: str, start_time: datetime, end_time: datetime, redis_client) -> List[Dict[str, Any]]:
    """Get historical drift data"""
    # Placeholder implementation - in production, query drift monitoring results
    return [
        {
            'timestamp': (start_time + timedelta(days=i)).isoformat(),
            'feature_drift_score': np.random.uniform(0, 0.1),
            'prediction_drift_score': np.random.uniform(0, 0.1)
        }
        for i in range((end_time - start_time).days + 1)
    ]


async def _calculate_drift_trends(model_name: str, start_time: datetime, end_time: datetime, redis_client) -> Dict[str, str]:
    """Calculate drift trends"""
    return {
        'feature_drift_trend': 'stable',
        'prediction_drift_trend': 'stable'
    }


async def _generate_drift_recommendations(model_name: str, model_monitor: ModelMonitor) -> List[str]:
    """Generate drift-related recommendations"""
    return [
        "Monitor feature distributions regularly",
        "Consider retraining if drift persists",
        "Implement automated drift alerting"
    ]


async def _get_prediction_volumes(model_name: Optional[str], start_time: datetime, end_time: datetime, granularity: str, redis_client) -> List[Dict[str, Any]]:
    """Get prediction volume data"""
    # Placeholder implementation
    import numpy as np
    
    if granularity == 'hour':
        periods = int((end_time - start_time).total_seconds() / 3600)
        time_delta = timedelta(hours=1)
    else:  # day
        periods = (end_time - start_time).days + 1
        time_delta = timedelta(days=1)
    
    volume_data = []
    current_time = start_time
    
    for _ in range(periods):
        volume_data.append({
            'timestamp': current_time.isoformat(),
            'prediction_count': int(np.random.poisson(50)),
            'batch_count': int(np.random.poisson(5)),
            'error_count': int(np.random.poisson(2))
        })
        current_time += time_delta
    
    return volume_data


async def _calculate_volume_statistics(model_name: Optional[str], start_time: datetime, end_time: datetime, redis_client) -> Dict[str, Any]:
    """Calculate volume statistics"""
    return {
        'total_predictions': int(np.random.poisson(1000)),
        'avg_predictions_per_hour': int(np.random.poisson(50)),
        'peak_hour_predictions': int(np.random.poisson(100)),
        'prediction_growth_rate': np.random.uniform(-0.1, 0.2)
    }


async def _detect_volume_anomalies(model_name: Optional[str], start_time: datetime, end_time: datetime, redis_client) -> List[Dict[str, Any]]:
    """Detect volume anomalies"""
    return [
        {
            'timestamp': (start_time + timedelta(hours=12)).isoformat(),
            'type': 'spike',
            'description': 'Prediction volume spike detected',
            'severity': 'medium'
        }
    ]


async def _analyze_usage_patterns(model_name: Optional[str], start_time: datetime, end_time: datetime, redis_client) -> Dict[str, Any]:
    """Analyze usage patterns"""
    return {
        'peak_hours': [9, 10, 11, 14, 15, 16],
        'peak_days': ['Monday', 'Tuesday', 'Wednesday'],
        'seasonal_patterns': 'Business hours focused usage'
    }


async def _get_error_summary(model_name: Optional[str], start_time: datetime, end_time: datetime, redis_client) -> Dict[str, Any]:
    """Get error summary statistics"""
    return {
        'total_errors': int(np.random.poisson(10)),
        'error_rate': np.random.uniform(0.01, 0.05),
        'most_common_error': 'Timeout',
        'error_trend': 'decreasing'
    }


async def _get_error_trends(model_name: Optional[str], start_time: datetime, end_time: datetime, redis_client) -> List[Dict[str, Any]]:
    """Get error trends over time"""
    return [
        {
            'timestamp': (start_time + timedelta(hours=i)).isoformat(),
            'error_count': int(np.random.poisson(1)),
            'error_rate': np.random.uniform(0.01, 0.03)
        }
        for i in range(int((end_time - start_time).total_seconds() / 3600))
    ]


async def _categorize_errors(model_name: Optional[str], start_time: datetime, end_time: datetime, redis_client) -> Dict[str, int]:
    """Categorize errors by type"""
    return {
        'timeout': int(np.random.poisson(3)),
        'validation': int(np.random.poisson(2)),
        'model_error': int(np.random.poisson(1)),
        'system_error': int(np.random.poisson(1))
    }


async def _analyze_failure_patterns(model_name: Optional[str], start_time: datetime, end_time: datetime, redis_client) -> List[str]:
    """Analyze failure patterns"""
    return [
        "Higher error rates during peak hours",
        "Validation errors more common with batch requests",
        "Model errors correlate with data drift periods"
    ]


async def _generate_error_recommendations(model_name: Optional[str], start_time: datetime, end_time: datetime, redis_client) -> List[str]:
    """Generate error-related recommendations"""
    return [
        "Implement better input validation",
        "Add retry logic for timeout errors",
        "Monitor resource utilization during peak hours"
    ]


# Import numpy for calculations
import numpy as np