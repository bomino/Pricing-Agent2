"""
Pydantic models for request/response schemas
"""
from typing import List, Dict, Any, Optional, Union
from decimal import Decimal
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict, validator
from enum import Enum


# Base schemas
class TimestampMixin(BaseModel):
    """Mixin for timestamp fields"""
    created_at: datetime
    updated_at: datetime


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=25, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    
    @classmethod
    def create(cls, items: List[Any], total: int, params: PaginationParams):
        total_pages = (total + params.page_size - 1) // params.page_size
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
            has_next=params.page < total_pages,
            has_previous=params.page > 1,
        )


# Enums
class PredictionStatus(str, Enum):
    """Prediction status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ModelType(str, Enum):
    """Model types"""
    PRICE_PREDICTOR = "price_predictor"
    ANOMALY_DETECTOR = "anomaly_detector"
    DEMAND_FORECASTER = "demand_forecaster"


class PriceType(str, Enum):
    """Price types"""
    QUOTE = "quote"
    CONTRACT = "contract"
    MARKET = "market"
    PREDICTED = "predicted"
    SHOULD_COST = "should_cost"


# Prediction schemas
class PricePredictionRequest(BaseModel):
    """Price prediction request"""
    material_id: str = Field(..., description="Material ID")
    quantity: Decimal = Field(..., gt=0, description="Quantity")
    unit_of_measure: str = Field(..., description="Unit of measure")
    supplier_id: Optional[str] = Field(None, description="Supplier ID (optional)")
    delivery_date: Optional[date] = Field(None, description="Required delivery date")
    region: Optional[str] = Field(None, description="Delivery region")
    payment_terms: Optional[str] = Field(None, description="Payment terms")
    specifications: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Material specifications")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    
    model_config = ConfigDict(
        json_encoders={
            Decimal: str
        }
    )


class PricePredictionResponse(BaseModel):
    """Price prediction response"""
    material_id: str
    quantity: Decimal
    predicted_price: Decimal
    unit_price: Decimal
    currency: str = "USD"
    confidence_score: float = Field(..., ge=0, le=1)
    prediction_interval: Dict[str, Decimal] = Field(..., description="Lower and upper bounds")
    model_version: str
    features_used: List[str]
    similar_quotes: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    
    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
    )


class BatchPredictionRequest(BaseModel):
    """Batch prediction request"""
    predictions: List[PricePredictionRequest] = Field(..., max_items=1000)
    async_processing: bool = Field(default=False, description="Process asynchronously")
    callback_url: Optional[str] = Field(None, description="Callback URL for async results")
    
    @validator('predictions')
    def validate_predictions_not_empty(cls, v):
        if not v:
            raise ValueError('Predictions list cannot be empty')
        return v


class BatchPredictionResponse(BaseModel):
    """Batch prediction response"""
    batch_id: str
    status: PredictionStatus
    total_predictions: int
    completed_predictions: int
    failed_predictions: int
    results: List[PricePredictionResponse] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    processing_time_seconds: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# Analytics schemas
class AnomalyDetectionRequest(BaseModel):
    """Anomaly detection request"""
    prices: List[Dict[str, Any]] = Field(..., min_items=1)
    sensitivity: float = Field(default=0.1, ge=0.01, le=0.5, description="Anomaly sensitivity")
    include_explanations: bool = Field(default=True, description="Include explanation for anomalies")


class AnomalyDetectionResponse(BaseModel):
    """Anomaly detection response"""
    anomalies: List[Dict[str, Any]]
    anomaly_count: int
    total_samples: int
    anomaly_rate: float = Field(..., ge=0, le=1)
    model_version: str
    sensitivity_used: float
    created_at: datetime


class TrendAnalysisRequest(BaseModel):
    """Trend analysis request"""
    material_id: str
    period_days: int = Field(default=90, ge=7, le=365)
    include_forecast: bool = Field(default=False)
    forecast_days: int = Field(default=30, ge=1, le=90)


class TrendAnalysisResponse(BaseModel):
    """Trend analysis response"""
    material_id: str
    period: Dict[str, date]
    trend_direction: str = Field(..., description="up, down, or stable")
    trend_strength: float = Field(..., ge=0, le=1)
    price_statistics: Dict[str, Decimal]
    trend_points: List[Dict[str, Any]]
    forecast: Optional[List[Dict[str, Any]]] = None
    seasonality: Dict[str, Any]
    created_at: datetime
    
    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            date: lambda v: v.isoformat(),
        }
    )


class DemandForecastRequest(BaseModel):
    """Demand forecast request"""
    material_id: str
    forecast_periods: int = Field(default=30, ge=1, le=365)
    include_confidence_intervals: bool = Field(default=True)
    seasonality_adjustment: bool = Field(default=True)
    holiday_effects: bool = Field(default=True)


class DemandForecastResponse(BaseModel):
    """Demand forecast response"""
    material_id: str
    forecast_periods: int
    forecast_data: List[Dict[str, Any]]
    model_performance: Dict[str, float]
    seasonality_components: Dict[str, List[Dict[str, Any]]]
    trend_component: List[Dict[str, Any]]
    uncertainty_intervals: Optional[Dict[str, List[Dict[str, Any]]]] = None
    created_at: datetime


# Model management schemas
class ModelInfo(BaseModel):
    """Model information"""
    name: str
    version: str
    model_type: str
    created_at: datetime
    performance_metrics: Dict[str, float]
    features: List[str]
    is_loaded: bool
    health_status: str
    last_used: datetime
    prediction_count: int

class ModelTrainingRequest(BaseModel):
    """Model training request"""
    model_type: str = Field(..., description="Type of model to train")
    config: Dict[str, Any] = Field(default_factory=dict, description="Training configuration")

class ModelTrainingResponse(BaseModel):
    """Model training response"""
    model_type: str
    status: str
    training_id: str
    started_at: datetime
    message: str

class ModelHealthReport(BaseModel):
    """Model health report"""
    model_name: str
    overall_health: str
    health_score: float
    checks: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    monitored_at: datetime


# Analytics and reporting schemas
class AnalyticsReport(BaseModel):
    """Analytics report"""
    report_type: str
    time_period: Dict[str, datetime]
    metrics: Dict[str, Any]
    generated_at: datetime

class DriftReport(BaseModel):
    """Data drift report"""
    model_name: str
    drift_detected: bool
    drift_score: float
    affected_features: List[str]
    recommendations: List[str]
    generated_at: datetime

class PerformanceReport(BaseModel):
    """Performance monitoring report"""
    model_name: str
    performance_metrics: Dict[str, float]
    performance_trend: str
    issues_detected: List[str]
    generated_at: datetime


# Feature engineering schemas
class FeatureRequest(BaseModel):
    """Feature extraction request"""
    material_id: str
    timestamp: datetime
    context: Dict[str, Any] = Field(default_factory=dict)


class FeatureResponse(BaseModel):
    """Feature extraction response"""
    material_id: str
    features: Dict[str, Any]
    feature_version: str
    computed_at: datetime
    cache_hit: bool


# Error schemas
class ErrorDetail(BaseModel):
    """Error detail"""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response"""
    error: ErrorDetail
    request_id: Optional[str] = None
    timestamp: datetime
    path: Optional[str] = None


# WebSocket schemas
class WebSocketMessage(BaseModel):
    """WebSocket message base"""
    type: str
    timestamp: datetime
    data: Dict[str, Any]


class PriceUpdateMessage(WebSocketMessage):
    """Price update WebSocket message"""
    type: str = "price_update"
    material_id: str
    old_price: Decimal
    new_price: Decimal
    price_change_percent: float
    source: str


class AnomalyAlertMessage(WebSocketMessage):
    """Anomaly alert WebSocket message"""
    type: str = "anomaly_alert"
    material_id: str
    anomaly_score: float
    current_price: Decimal
    expected_price: Decimal
    severity: str


class PredictionCompleteMessage(WebSocketMessage):
    """Prediction completion WebSocket message"""
    type: str = "prediction_complete"
    batch_id: str
    status: PredictionStatus
    results_count: int
    errors_count: int


# Health check schemas
class HealthStatus(BaseModel):
    """Health check status"""
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]
    uptime_seconds: float


class ModelHealthStatus(BaseModel):
    """Model health status"""
    model_id: str
    status: str
    last_prediction: Optional[datetime] = None
    error_rate: float
    average_latency_ms: float