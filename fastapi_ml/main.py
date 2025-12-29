"""
FastAPI ML Service Main Application
"""
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import uvicorn
import redis.asyncio as redis
from prometheus_client import make_asgi_app, Counter, Histogram, Gauge
import structlog
from datetime import datetime

from config import settings
from dependencies import get_redis, get_db
from api.v1 import predictions, analytics, models as model_endpoints
from api import websockets
from services.model_registry import ModelRegistry
from services.ml_service import MLService


# Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
MODEL_PREDICTIONS = Counter('ml_predictions_total', 'Total ML predictions', ['model', 'status'])
ACTIVE_CONNECTIONS = Gauge('websocket_connections_active', 'Active WebSocket connections')

# Logger
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting ML service...")
    
    # Initialize services
    app.state.redis = redis.from_url(settings.REDIS_URL)
    app.state.model_registry = ModelRegistry()
    app.state.ml_service = MLService(app.state.model_registry)
    
    # Load ML models
    try:
        await app.state.model_registry.load_models()
        logger.info("ML models loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load ML models: {e}")
        # Continue without models for now
    
    # Health check
    logger.info("ML service started successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down ML service...")
    await app.state.redis.close()
    logger.info("ML service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="AI Pricing Agent - ML Service",
    description="Machine Learning service for pricing predictions and analytics",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)


# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all HTTP requests with timing"""
    start_time = datetime.utcnow()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    process_time = (datetime.utcnow() - start_time).total_seconds()
    
    # Update metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    REQUEST_DURATION.observe(process_time)
    
    # Log request
    logger.info(
        "HTTP request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=f"{process_time:.3f}s",
        user_agent=request.headers.get("user-agent", ""),
        client_ip=request.client.host,
    )
    
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    logger.error(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"http_{exc.status_code}",
                "message": exc.detail,
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(
        "Unhandled exception",
        exception=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred",
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
            }
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers"""
    try:
        # Check Redis connection
        redis_client = app.state.redis
        await redis_client.ping()
        
        # Check model registry
        model_status = await app.state.model_registry.get_health_status()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "services": {
                "redis": "healthy",
                "models": model_status,
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
            }
        )


# Readiness check
@app.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes"""
    try:
        # Check if models are loaded
        model_count = await app.state.model_registry.get_loaded_model_count()
        
        if model_count == 0:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "reason": "No models loaded",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "loaded_models": model_count,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


# Include routers
app.include_router(
    predictions.router,
    prefix="/api/v1/predictions",
    tags=["predictions"]
)

app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["analytics"]
)

app.include_router(
    model_endpoints.router,
    prefix="/api/v1/models",
    tags=["models"]
)

app.include_router(
    websockets.router,
    prefix="/ws",
    tags=["websockets"]
)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# Custom OpenAPI schema
def custom_openapi():
    """Custom OpenAPI schema with authentication details"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
        "ServiceKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-ML-Service-Key",
        }
    }
    
    # Add security to all operations
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if method in ["get", "post", "put", "patch", "delete"]:
                openapi_schema["paths"][path][method]["security"] = [
                    {"BearerAuth": []},
                    {"ServiceKeyAuth": []}
                ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AI Pricing Agent - ML Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/health",
        "ready": "/ready",
        "metrics": "/metrics",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
        access_log=True,
        server_header=False,
        date_header=False,
    )