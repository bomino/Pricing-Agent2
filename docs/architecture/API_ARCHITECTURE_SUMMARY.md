# AI Pricing Agent - Backend API Architecture

## Overview

This document provides a comprehensive overview of the backend API architecture implemented for the AI Pricing Agent system. The architecture follows a Django-centric approach with FastAPI as a specialized ML sidecar service, designed for production-ready deployment with proper separation of concerns.

## Architecture Components

### 1. Django Main Application (Port 8000)

**Technology Stack:**
- Django 5.0+ with Django REST Framework
- PostgreSQL + TimescaleDB for time-series data
- Redis for caching and session management
- Celery for background tasks
- HTMX + Alpine.js for frontend interactions

**Key Features:**
- Multi-tenant organization support
- Comprehensive authentication and authorization
- Audit logging and compliance
- Real-time WebSocket support via Django Channels
- HTMX-friendly API endpoints

### 2. FastAPI ML Service (Port 8001)

**Technology Stack:**
- FastAPI 0.110+ with Pydantic v2
- Async architecture with asyncio
- Redis for caching ML predictions
- MLflow for model management
- Prometheus metrics integration
- WebSocket support for real-time ML updates

**Key Features:**
- Production-ready ML model serving
- Batch prediction processing
- Real-time anomaly detection
- Advanced analytics and forecasting
- Model monitoring and drift detection

## API Design Patterns

### 1. URL Structure and Versioning

```
# Django API Endpoints
/api/v1/materials/                    # Material CRUD operations
/api/v1/prices/                       # Price data management
/api/v1/suppliers/                    # Supplier management
/api/v1/rfqs/                         # Request for Quote workflows
/api/v1/quotes/                       # Quote management
/api/v1/benchmarks/                   # Price benchmarking
/api/v1/alerts/                       # Price alert configuration
/api/v1/analytics/                    # Business analytics

# FastAPI ML Endpoints
/api/v1/predictions/price             # Single price prediction
/api/v1/predictions/batch             # Batch predictions
/api/v1/analytics/anomalies           # Anomaly detection
/api/v1/analytics/trends              # Trend analysis
/api/v1/analytics/forecast            # Demand forecasting
/api/v1/models/                       # Model management

# WebSocket Endpoints
/ws/prices/                           # Real-time price updates
/ws/notifications/                    # System notifications
/ws/predictions/{batch_id}/           # Prediction status updates
```

### 2. Authentication and Authorization

**Multi-layered Authentication:**

1. **Session Authentication** (Web UI)
   - Django's built-in session management
   - CSRF protection for forms
   - Secure cookie configuration

2. **JWT Authentication** (API and Inter-service)
   - Custom JWT implementation with jose library
   - Service-to-service authentication
   - WebSocket authentication support

3. **API Key Authentication** (External integrations)
   - Hashed API keys with expiration
   - Granular permission control
   - Usage tracking and rate limiting

4. **Organization-based Authorization**
   - Multi-tenant data isolation
   - Role-based access control (RBAC)
   - Resource-level permissions

### 3. Error Handling and Validation

**Standardized Error Responses:**

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid input data",
    "details": {
      "quantity": ["Must be greater than zero"],
      "material_id": ["Material not found"]
    }
  },
  "status_code": 400,
  "timestamp": "2025-01-23T10:30:00Z",
  "request_id": "req_12345"
}
```

**Key Features:**
- Custom exception hierarchy
- Automatic error logging and monitoring
- User-friendly error messages
- Development vs. production error detail levels
- Request tracking for debugging

### 4. Data Validation

**Django Serializers (DRF):**
- Comprehensive field validation
- Cross-field validation logic
- Organization-scoped validation
- Custom validator classes

**Pydantic Models (FastAPI):**
- Type-safe request/response validation
- Automatic OpenAPI schema generation
- Performance-optimized serialization
- Custom validation methods

### 5. Rate Limiting and Throttling

**Implementation:**

```python
# Django Settings
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'ml_predict': '60/minute',
        'bulk_operations': '10/hour',
    }
}

# FastAPI Rate Limiter
@rate_limit("ml_predict")
async def predict_price(request: PricePredictionRequest):
    # Implementation
```

**Features:**
- Redis-based distributed rate limiting
- Per-user and per-IP rate limits
- Burst allowance for peak usage
- Custom rate limit headers
- Graceful degradation

### 6. Caching Strategy

**Multi-layer Caching:**

1. **Application Layer (Redis)**
   - API response caching
   - ML prediction caching
   - Session data storage
   - Task queue management

2. **Database Layer**
   - Query result caching
   - Connection pooling
   - Read replica support

3. **ML Predictions**
   - Feature caching (10 minutes)
   - Prediction result caching (5 minutes)
   - Model metadata caching (1 hour)

### 7. Real-time Features (WebSockets)

**Django Channels Implementation:**
- Price update notifications
- System alerts and notifications
- Workflow status updates
- Chat/messaging support

**FastAPI WebSocket Implementation:**
- ML prediction progress
- Real-time analytics updates
- Model performance monitoring
- Custom event streaming

## Data Models and Schema

### 1. Core Models

**Organization Model:**
```python
class Organization(TimestampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    type = models.CharField(max_length=20, choices=ORGANIZATION_TYPES)
    settings = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
```

**Material Model:**
```python
class Material(TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL)
    specifications = models.JSONField(default=dict)
    list_price = models.DecimalField(max_digits=15, decimal_places=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
```

### 2. Time-series Data (TimescaleDB)

**Price Model:**
```python
class Price(models.Model):
    time = models.DateTimeField(db_index=True)  # Partition key
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=15, decimal_places=4)
    price_type = models.CharField(max_length=20, choices=PRICE_TYPES)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4)
    metadata = models.JSONField(default=dict)
```

### 3. ML Integration Models

**Pydantic Schemas:**
```python
class PricePredictionRequest(BaseModel):
    material_id: str
    quantity: Decimal
    supplier_id: Optional[str] = None
    delivery_date: Optional[date] = None
    specifications: Dict[str, Any] = Field(default_factory=dict)
    
class PricePredictionResponse(BaseModel):
    predicted_price: Decimal
    confidence_score: float
    prediction_interval: Dict[str, Decimal]
    model_version: str
    features_used: List[str]
```

## Performance Optimizations

### 1. Database Optimizations

**Indexing Strategy:**
```sql
-- Composite indexes for common queries
CREATE INDEX idx_prices_material_time ON prices(material_id, time DESC);
CREATE INDEX idx_prices_supplier_time ON prices(supplier_id, time DESC);

-- GIN indexes for JSON fields
CREATE INDEX idx_materials_specs ON materials USING GIN (specifications);
CREATE INDEX idx_prices_metadata ON prices USING GIN (metadata);

-- Partial indexes for filtered queries
CREATE INDEX idx_active_materials ON materials (organization_id, status) 
WHERE status = 'active';
```

**Query Optimization:**
- Select related for foreign keys
- Prefetch related for reverse foreign keys
- Database-level aggregations
- Pagination for large datasets
- Connection pooling

### 2. Caching Strategies

**Cache Keys Pattern:**
```python
# Hierarchical cache keys
f"material:{org_id}:{material_id}"
f"price_history:{material_id}:{days}:{price_type}"
f"prediction:{material_id}:{quantity_hash}:{context_hash}"
f"benchmark:{material_id}:{benchmark_type}:{period}"
```

**Cache Invalidation:**
- Event-driven cache invalidation
- TTL-based expiration
- Dependency-based invalidation
- Graceful cache warming

### 3. Async Processing

**Background Tasks (Celery):**
- Bulk data processing
- Report generation
- Email notifications
- Data synchronization
- ML model training

**Async Operations (FastAPI):**
- Concurrent ML predictions
- Parallel data fetching
- Non-blocking I/O operations
- Streaming responses

## Security Implementation

### 1. Data Protection

**Encryption:**
- Database encryption at rest
- TLS 1.3 for data in transit
- Field-level encryption for PII
- Secure key management

**Input Validation:**
- SQL injection prevention
- XSS protection
- CSRF tokens
- Parameter validation
- File upload security

### 2. Access Control

**Authentication:**
- Multi-factor authentication support
- Account lockout protection
- Password complexity requirements
- Session management

**Authorization:**
- Role-based access control
- Resource-level permissions
- Organization data isolation
- API scope limitations

### 3. Audit and Compliance

**Audit Logging:**
```python
class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)
```

**Compliance Features:**
- GDPR data handling
- Data retention policies
- Right to be forgotten
- Data export capabilities

## API Documentation

### 1. OpenAPI/Swagger Integration

**FastAPI Auto-generation:**
- Automatic schema generation
- Interactive API documentation
- Type-safe request/response examples
- Authentication flow documentation

**Django Integration:**
- DRF schema generation
- Custom schema extensions
- Endpoint documentation
- Permission documentation

### 2. API Versioning Strategy

**URL Path Versioning:**
```
/api/v1/materials/  # Version 1
/api/v2/materials/  # Version 2 (future)
```

**Version Management:**
- Backward compatibility
- Deprecation warnings
- Migration guides
- Client SDK updates

## Monitoring and Observability

### 1. Metrics Collection

**Prometheus Metrics:**
```python
# Request metrics
REQUEST_COUNT = Counter('http_requests_total', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds')

# ML metrics
MODEL_PREDICTIONS = Counter('ml_predictions_total', ['model', 'status'])
PREDICTION_LATENCY = Histogram('ml_prediction_duration_seconds')

# Business metrics
PRICE_UPDATES = Counter('price_updates_total', ['material_type'])
ANOMALIES_DETECTED = Counter('price_anomalies_total', ['severity'])
```

### 2. Logging Strategy

**Structured Logging:**
```python
logger.info(
    "Price prediction completed",
    material_id=material_id,
    prediction_time_ms=duration,
    confidence_score=confidence,
    user_id=user.id,
    organization_id=org.id,
)
```

### 3. Health Checks

**Endpoint Monitoring:**
- Database connectivity
- Redis availability
- ML service status
- External service health
- Resource utilization

## Deployment Considerations

### 1. Container Architecture

**Docker Services:**
```yaml
services:
  django:
    build: ./django_app
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
    
  fastapi:
    build: ./fastapi_ml
    ports: ["8001:8001"]
    depends_on: [postgres, redis]
    
  postgres:
    image: timescale/timescaledb:latest-pg16
    
  redis:
    image: redis:7-alpine
    
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
```

### 2. Scalability

**Horizontal Scaling:**
- Stateless application design
- Load balancer configuration
- Database read replicas
- Redis cluster setup
- CDN integration

**Vertical Scaling:**
- Resource monitoring
- Automatic scaling rules
- Performance thresholds
- Cost optimization

### 3. CI/CD Pipeline

**Automated Testing:**
- Unit tests (>80% coverage)
- Integration tests
- API contract tests
- Performance tests
- Security scans

**Deployment Strategy:**
- Blue-green deployments
- Database migrations
- Feature flags
- Rollback procedures

## File Structure Summary

```
django_app/
├── pricing_agent/
│   ├── settings/          # Environment-specific settings
│   ├── urls.py           # Main URL routing with API versioning
│   └── asgi.py           # WebSocket and async support
├── apps/
│   ├── core/             # Shared functionality
│   │   ├── models.py     # Base models, Organization, Category
│   │   ├── authentication.py  # JWT, ML service client
│   │   ├── middleware.py # Audit, organization context
│   │   ├── exceptions.py # Custom exception handling
│   │   ├── pagination.py # API pagination classes
│   │   └── renderers.py  # HTMX, CSV, Excel renderers
│   ├── accounts/         # User management
│   │   ├── models.py     # Extended User, Profile, Membership
│   │   └── api/          # User API endpoints
│   ├── pricing/          # Pricing engine
│   │   ├── models.py     # Material, Price, Benchmark models
│   │   ├── api/
│   │   │   ├── serializers.py  # DRF serializers
│   │   │   └── viewsets.py     # API viewsets
│   │   └── filters.py    # Django Filter integration
│   └── procurement/      # Procurement workflows
│       ├── models.py     # Supplier, RFQ, Quote, Contract
│       └── api/          # Procurement API endpoints

fastapi_ml/
├── main.py               # FastAPI application with middleware
├── config.py             # ML service configuration
├── dependencies.py       # Auth, rate limiting, services
├── models/
│   └── schemas.py        # Pydantic request/response models
├── api/
│   ├── v1/
│   │   ├── predictions.py    # ML prediction endpoints
│   │   └── analytics.py      # Analytics endpoints
│   └── websockets.py     # Real-time WebSocket endpoints
└── services/             # ML business logic
```

## Key Implementation Files

### Django Core Files:
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\pricing_agent\settings\base.py`** - Comprehensive Django configuration
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\pricing_agent\urls.py`** - URL routing with API versioning
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\apps\core\authentication.py`** - JWT authentication and ML service client
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\apps\core\middleware.py`** - Audit logging and organization middleware

### FastAPI ML Service Files:
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\fastapi_ml\main.py`** - FastAPI application with comprehensive middleware
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\fastapi_ml\models\schemas.py`** - Pydantic models for all ML operations
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\fastapi_ml\api\v1\predictions.py`** - ML prediction endpoints with batch processing
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\fastapi_ml\api\websockets.py`** - Real-time WebSocket implementation

### API Implementation Files:
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\apps\pricing\api\serializers.py`** - DRF serializers with validation
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\apps\pricing\api\viewsets.py`** - REST API viewsets with ML integration
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\apps\pricing\filters.py`** - Advanced filtering capabilities

### Data Models:
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\apps\core\models.py`** - Core models with multi-tenancy
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\apps\pricing\models.py`** - Pricing and material models with TimescaleDB
- **`C:\Users\lawry\Documents\VSTX Projects\VSTX-Project\PricingProject\Pricing_Agent\django_app\apps\procurement\models.py`** - Procurement workflow models

## Next Steps

1. **Environment Setup:**
   - Configure environment variables
   - Set up development database
   - Initialize Redis instance
   - Configure ML model storage

2. **Database Initialization:**
   - Run Django migrations
   - Set up TimescaleDB hypertables
   - Load initial data/fixtures
   - Configure database indexes

3. **Service Integration:**
   - Configure service-to-service authentication
   - Set up reverse proxy (NGINX)
   - Configure SSL certificates
   - Set up monitoring and logging

4. **Testing:**
   - Run comprehensive test suite
   - Perform load testing
   - Security penetration testing
   - API contract testing

This implementation provides a production-ready, scalable backend API architecture that supports advanced ML capabilities while maintaining enterprise-grade security, performance, and reliability standards.