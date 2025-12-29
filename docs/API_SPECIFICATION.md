# API Specification - AI Pricing Agent

## Overview

This document describes the REST API and ML Service API specifications for the AI Pricing Agent system.

---

## 🔐 Authentication

### OAuth2 Bearer Token

All API requests require authentication using Bearer tokens.

```http
Authorization: Bearer <token>
```

### Endpoints

#### Login
```http
POST /api/v1/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

Response: 200 OK
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "organization": "ACME Corp",
    "role": "buyer"
  }
}
```

#### Refresh Token
```http
POST /api/v1/auth/refresh/
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

Response: 200 OK
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "expires_in": 3600
}
```

---

## 📦 Materials API

### List Materials
```http
GET /api/v1/materials/
Query Parameters:
  - page: integer (default: 1)
  - page_size: integer (default: 20, max: 100)
  - search: string (search in name, code, description)
  - category: string (filter by category)
  - status: string (active, inactive)
  - organization: uuid

Response: 200 OK
{
  "count": 523,
  "next": "http://api/v1/materials/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "code": "MAT-001",
      "name": "Steel Rebar 12mm",
      "description": "High-strength steel reinforcement bar",
      "category": {
        "id": "uuid",
        "name": "Steel Products"
      },
      "unit_of_measure": "ton",
      "specifications": {
        "diameter": "12mm",
        "grade": "Fe500",
        "length": "12m"
      },
      "current_price": {
        "value": 850.00,
        "currency": "USD",
        "updated_at": "2025-08-23T10:00:00Z"
      },
      "price_trend": "increasing",
      "status": "active"
    }
  ]
}
```

### Get Material Detail
```http
GET /api/v1/materials/{id}/

Response: 200 OK
{
  "id": "uuid",
  "code": "MAT-001",
  "name": "Steel Rebar 12mm",
  "description": "High-strength steel reinforcement bar",
  "category": {...},
  "specifications": {...},
  "current_price": {...},
  "price_history": [
    {
      "date": "2025-08-23",
      "price": 850.00,
      "source": "supplier_quote"
    }
  ],
  "suppliers": [
    {
      "id": "uuid",
      "name": "Steel Corp",
      "last_price": 845.00,
      "rating": 4.5
    }
  ],
  "predictions": {
    "next_month": 865.00,
    "confidence": 0.87
  }
}
```

### Create Material
```http
POST /api/v1/materials/
Content-Type: application/json

{
  "code": "MAT-002",
  "name": "Concrete Mix C25",
  "description": "Ready-mix concrete",
  "category_id": "uuid",
  "unit_of_measure": "m3",
  "specifications": {
    "strength": "25 MPa",
    "slump": "100mm"
  }
}

Response: 201 Created
```

---

## 🏢 Suppliers API

### List Suppliers
```http
GET /api/v1/suppliers/
Query Parameters:
  - status: string (active, inactive, blocked)
  - category: string
  - rating_min: float
  - country: string

Response: 200 OK
{
  "count": 145,
  "results": [
    {
      "id": "uuid",
      "name": "Steel Corp Industries",
      "code": "SUP-001",
      "category": "Steel Products",
      "contact": {
        "email": "sales@steelcorp.com",
        "phone": "+1-555-0100",
        "address": "123 Industrial Ave"
      },
      "ratings": {
        "overall": 4.5,
        "quality": 4.7,
        "delivery": 4.3,
        "price": 4.4
      },
      "performance": {
        "on_time_delivery": 92.5,
        "defect_rate": 0.3,
        "response_time_hours": 4.2
      },
      "status": "active"
    }
  ]
}
```

### Supplier Performance Analytics
```http
GET /api/v1/suppliers/{id}/analytics/
Query Parameters:
  - period: string (30d, 90d, 1y)

Response: 200 OK
{
  "supplier_id": "uuid",
  "period": "90d",
  "metrics": {
    "total_orders": 45,
    "total_value": 1250000.00,
    "avg_order_value": 27777.78,
    "on_time_delivery_rate": 91.1,
    "quality_issues": 2,
    "price_competitiveness": 0.85
  },
  "trends": {
    "price_trend": "stable",
    "performance_trend": "improving"
  },
  "comparisons": {
    "vs_market_avg": {
      "price": -3.2,
      "delivery": +5.1,
      "quality": +2.3
    }
  }
}
```

---

## 📋 RFQ (Request for Quotation) API

### Create RFQ
```http
POST /api/v1/rfqs/
Content-Type: application/json

{
  "title": "Q3 2025 Steel Requirements",
  "description": "Quarterly steel procurement",
  "items": [
    {
      "material_id": "uuid",
      "quantity": 100,
      "delivery_date": "2025-09-15",
      "specifications": "As per standard"
    }
  ],
  "suppliers": ["uuid1", "uuid2", "uuid3"],
  "response_deadline": "2025-08-30T17:00:00Z",
  "delivery_location": "Site A",
  "payment_terms": "Net 30",
  "auto_analyze": true
}

Response: 201 Created
{
  "id": "uuid",
  "rfq_number": "RFQ-2025-0892",
  "status": "published",
  "created_at": "2025-08-23T10:30:00Z"
}
```

### Get RFQ Status
```http
GET /api/v1/rfqs/{id}/status/

Response: 200 OK
{
  "rfq_id": "uuid",
  "status": "evaluating",
  "suppliers_invited": 5,
  "responses_received": 3,
  "responses_pending": 2,
  "deadline": "2025-08-30T17:00:00Z",
  "time_remaining": "7 days",
  "quotes": [
    {
      "supplier": "Steel Corp",
      "status": "submitted",
      "total_value": 85000.00,
      "submitted_at": "2025-08-24T09:15:00Z"
    }
  ]
}
```

---

## 💰 Pricing API

### Get Price Predictions
```http
POST /api/v1/prices/predict/
Content-Type: application/json

{
  "material_id": "uuid",
  "quantity": 100,
  "delivery_date": "2025-09-15",
  "location": "New York",
  "include_confidence": true
}

Response: 200 OK
{
  "material": {
    "id": "uuid",
    "name": "Steel Rebar 12mm"
  },
  "predictions": {
    "point_estimate": 865.50,
    "confidence_interval": {
      "lower": 845.00,
      "upper": 886.00,
      "confidence": 0.95
    },
    "factors": {
      "seasonality": +2.1,
      "market_trend": +1.5,
      "location": -0.8
    }
  },
  "benchmark": {
    "market_average": 860.00,
    "percentile": 48
  },
  "recommendation": "BUY_NOW",
  "explanation": "Prices expected to increase 3% over next month"
}
```

### Get Price History
```http
GET /api/v1/prices/history/
Query Parameters:
  - material_id: uuid (required)
  - period: string (1m, 3m, 6m, 1y)
  - granularity: string (daily, weekly, monthly)

Response: 200 OK
{
  "material_id": "uuid",
  "period": "3m",
  "data_points": [
    {
      "date": "2025-08-01",
      "price": 840.00,
      "volume": 250,
      "source": "market"
    },
    {
      "date": "2025-08-02",
      "price": 842.00,
      "volume": 180,
      "source": "quotes"
    }
  ],
  "statistics": {
    "mean": 845.50,
    "median": 844.00,
    "std_dev": 8.25,
    "min": 835.00,
    "max": 865.00,
    "trend": "increasing"
  }
}
```

### Price Alerts
```http
POST /api/v1/prices/alerts/
Content-Type: application/json

{
  "material_id": "uuid",
  "alert_type": "threshold",
  "condition": "below",
  "threshold": 800.00,
  "notification_channels": ["email", "sms"],
  "expires_at": "2025-12-31T23:59:59Z"
}

Response: 201 Created
{
  "id": "uuid",
  "status": "active",
  "created_at": "2025-08-23T11:00:00Z"
}
```

---

## 🤖 ML Service API (FastAPI)

### Base URL
```
http://localhost:8001/ml
```

### Price Prediction
```http
POST /ml/predict/price
Content-Type: application/json

{
  "material_code": "MAT-001",
  "features": {
    "quantity": 100,
    "lead_time_days": 30,
    "location": "NY",
    "season": "summer",
    "market_indicators": {
      "oil_price": 75.50,
      "steel_index": 102.3,
      "exchange_rate": 1.08
    }
  },
  "horizon_days": 30
}

Response: 200 OK
{
  "prediction": {
    "value": 865.50,
    "confidence": 0.87,
    "interval_95": [845.00, 886.00]
  },
  "model": {
    "name": "ensemble_v2.1",
    "version": "2.1.0",
    "last_trained": "2025-08-20T00:00:00Z"
  },
  "feature_importance": {
    "quantity": 0.25,
    "market_indicators.steel_index": 0.22,
    "lead_time_days": 0.18
  }
}
```

### Anomaly Detection
```http
POST /ml/detect/anomaly
Content-Type: application/json

{
  "price": 950.00,
  "material_code": "MAT-001",
  "supplier_id": "uuid",
  "context": {
    "quantity": 100,
    "recent_prices": [840, 845, 842, 848, 850]
  }
}

Response: 200 OK
{
  "is_anomaly": true,
  "anomaly_score": 0.92,
  "severity": "high",
  "explanation": "Price 12% above expected range",
  "suggested_action": "Request justification from supplier",
  "similar_cases": [
    {
      "date": "2025-07-15",
      "price": 920.00,
      "resolution": "Negotiated to 870.00"
    }
  ]
}
```

### Model Training
```http
POST /ml/train/model
Content-Type: application/json

{
  "model_type": "price_prediction",
  "dataset": "production",
  "parameters": {
    "test_size": 0.2,
    "cv_folds": 5,
    "feature_selection": true
  }
}

Response: 202 Accepted
{
  "job_id": "uuid",
  "status": "training",
  "estimated_time_minutes": 45,
  "webhook_url": "http://api/v1/ml/training/callback"
}
```

### Model Performance
```http
GET /ml/models/performance?model=price_prediction

Response: 200 OK
{
  "model": "price_prediction",
  "version": "2.1.0",
  "metrics": {
    "mae": 12.35,
    "rmse": 18.92,
    "mape": 1.45,
    "r2": 0.89
  },
  "validation": {
    "dataset_size": 50000,
    "test_size": 10000,
    "cross_validation_score": 0.87
  },
  "predictions_served": 12543,
  "avg_latency_ms": 45
}
```

---

## 📊 Analytics API

### Cost Savings Report
```http
GET /api/v1/analytics/cost-savings/
Query Parameters:
  - period: string (mtd, qtd, ytd)
  - organization: uuid

Response: 200 OK
{
  "period": "qtd",
  "total_spend": 5250000.00,
  "savings": {
    "amount": 787500.00,
    "percentage": 15.0,
    "vs_baseline": 525000.00
  },
  "breakdown": {
    "negotiation": 425000.00,
    "timing_optimization": 185000.00,
    "supplier_optimization": 177500.00
  },
  "top_opportunities": [
    {
      "material": "Steel Rebar",
      "potential_savings": 45000.00,
      "action": "Switch to Supplier B"
    }
  ]
}
```

### Dashboard Metrics
```http
GET /api/v1/analytics/dashboard/

Response: 200 OK
{
  "kpis": {
    "active_rfqs": 12,
    "pending_quotes": 8,
    "mtd_savings": 145000.00,
    "supplier_performance": 88.5,
    "prediction_accuracy": 86.7
  },
  "trends": {
    "cost_trend": [
      {"month": "Jun", "value": 1750000},
      {"month": "Jul", "value": 1680000},
      {"month": "Aug", "value": 1620000}
    ]
  },
  "alerts": [
    {
      "type": "price_increase",
      "material": "Copper Wire",
      "change": +5.2,
      "action_required": true
    }
  ]
}
```

---

## 🔄 WebSocket API

### Connection
```javascript
ws://localhost:8000/ws/pricing/

// Authentication
{
  "type": "auth",
  "token": "Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### Subscribe to Price Updates
```javascript
// Subscribe
{
  "type": "subscribe",
  "channel": "price_updates",
  "materials": ["uuid1", "uuid2"]
}

// Receive updates
{
  "type": "price_update",
  "data": {
    "material_id": "uuid",
    "price": 852.00,
    "change": +0.5,
    "timestamp": "2025-08-23T12:00:00Z"
  }
}
```

---

## 📝 Error Responses

### Standard Error Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "quantity",
        "message": "Must be greater than 0"
      }
    ],
    "request_id": "req_xyz123",
    "timestamp": "2025-08-23T12:00:00Z"
  }
}
```

### HTTP Status Codes
- `200 OK` - Successful request
- `201 Created` - Resource created
- `202 Accepted` - Request accepted for processing
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

---

## 🚦 Rate Limiting

### Limits
- **Standard tier**: 1000 requests/hour
- **Premium tier**: 10000 requests/hour
- **ML endpoints**: 100 requests/hour

### Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1629820800
```

---

## 🔍 Pagination

All list endpoints support pagination:

```http
GET /api/v1/materials/?page=2&page_size=50

Response Headers:
X-Total-Count: 523
X-Page-Count: 11
Link: <http://api/v1/materials/?page=3>; rel="next",
      <http://api/v1/materials/?page=1>; rel="prev",
      <http://api/v1/materials/?page=11>; rel="last"
```

---

## 📚 API Versioning

The API uses URL versioning:
- Current version: `v1`
- Base URL: `/api/v1/`
- Deprecation notice: 6 months
- Sunset period: 12 months

---

**Document Version**: 1.0
**Last Updated**: August 2025
**OpenAPI Spec**: `/api/schema/`