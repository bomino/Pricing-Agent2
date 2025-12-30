# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Pricing Agent for Manufacturing & Construction Procurement - An enterprise B2B platform that automates cost benchmarking, validates quotes, and generates should-cost models using ML to enable 10-15% cost reduction in procurement operations.

**Repository**: https://github.com/bomino/Pricing-Agent2
**Status**: ✅ Phase 1 & Phase 2 Complete (December 2024)
**Current Version**: 2.0

## Architecture

### Django-Centric with FastAPI ML Sidecar

```text
Django (Port 8000) - Primary Application
├── Web Interface (HTMX)
├── Business Logic & Workflows
├── Authentication & Authorization
├── Admin Panel
└── Database Models

FastAPI (Port 8001) - ML Service
├── Model Serving
├── Async Calculations
├── Real-time Processing
└── WebSocket Support
```

## Critical Development Commands

### Quick Start (Windows)

```bash
# Start all services
docker-compose -f docker-compose.simple.yml up -d

# View logs
docker-compose -f docker-compose.simple.yml logs -f django

# Access Django shell
docker exec -it pricing_django python manage.py shell

# Run migrations
docker exec -it pricing_django python manage.py migrate

# Create superuser
docker exec -it pricing_django python manage.py createsuperuser

# Collect static files
docker exec -it pricing_django python manage.py collectstatic --noinput
```

### Windows-Specific Setup

#### Automated Setup (Recommended)

```bash
# Start all services with interactive setup
./start-windows.bat

# Stop all services and clean up
./stop-windows.bat
```

The `start-windows.bat` script provides:
- Prerequisites check (Python, pip, Docker)
- Port availability verification
- Choice between local development and full Docker setup
- Automatic virtual environment management
- Database migrations and static files collection
- Optional superuser creation
- Optional Celery workers startup

#### Manual Setup

```bash
# For Windows development with local services (PostgreSQL, Redis, MailHog only)
docker-compose -f docker-compose.windows.yml up -d

# Then run Django locally
python django_app/manage.py runserver
```

### Testing Commands

```bash
# Run Django tests
docker exec -it pricing_django python manage.py test apps.data_ingestion

# Run all tests with coverage
make test coverage

# Run specific test suites
make test-unit           # Unit tests only
make test-integration    # Integration tests
make test-django        # Django-specific tests
make test-fastapi       # FastAPI-specific tests
make test-parallel       # Run tests in parallel
make test-performance    # Locust performance tests
make test-security       # Security tests

# Test specific components
make test-models         # Test Django models
make test-views          # Test Django views
make test-api-endpoints  # Test API endpoints

# Coverage reports
make coverage-html       # Generate HTML coverage report
make coverage-fail-under # Fail if coverage below 80%
```

### Code Quality

```bash
# Format code
make format

# Run linting
make lint

# Type checking
make type-check
```

## Project Structure

```text
pricing_agent/
├── django_app/                # Django main application
│   ├── manage.py
│   ├── pricing_agent/         # Project settings
│   ├── apps/                  # Django apps
│   │   ├── core/             # Core functionality
│   │   ├── accounts/         # User management
│   │   ├── data_ingestion/   # File upload & processing (ACTIVE)
│   │   ├── procurement/      # Procurement workflows
│   │   ├── pricing/          # Pricing engine
│   │   ├── analytics/        # Analytics & reporting
│   │   └── integrations/     # External integrations
│   ├── templates/            # HTMX templates
│   ├── static/               # Static files
│   └── tests/                # Django tests
├── fastapi_ml/               # FastAPI ML service (Ready for activation)
│   ├── main.py              # FastAPI app
│   ├── api/                 # API endpoints
│   ├── models/              # ML models
│   ├── services/            # Business logic
│   └── ml_artifacts/        # Trained models
├── infrastructure/           # Docker, K8s configurations
├── tests/                    # Cross-service tests
│   ├── performance/         # Locust performance tests
│   ├── security/           # Security tests
│   └── data_quality/       # Data validation tests
└── docs/                     # Documentation
```

## Key API Endpoints

### Django (Currently Active)

```text
/                                   # Dashboard with upload stats
/accounts/login/                   # Styled authentication page with animations
/accounts/logout/                  # Logout endpoint (POST only for security)
/accounts/profile/                 # User profile management
/analytics/                        # Analytics center with tabbed interface
/analytics/tab/insights/           # Key insights tab (HTMX)
/analytics/tab/trends/             # Trend analysis tab (HTMX)
/analytics/tab/predictions/        # Predictions tab (HTMX)
/analytics/tab/benchmarks/         # Benchmarking tab (HTMX)
/analytics/tab/reports/            # Reports tab (HTMX)
/data-ingestion/upload/            # File upload interface (Phase 0.5 - COMPLETE)
/data-ingestion/mapping/{id}/      # Column mapping UI
/data-ingestion/validation/{id}/   # Data validation review
/admin/                            # Django admin panel
```

### FastAPI ML (Ready for Week 2 Activation)

```text
/health                            # Health check
/api/v1/predictions/price/         # Price prediction
/api/v1/predictions/batch/         # Batch predictions
/api/v1/analytics/anomalies/       # Anomaly detection
/ws/prices/                        # WebSocket real-time prices
```

## Data Flow Architecture

### Current State

```text
[File Upload] → [Staging Table] → ❌ [Processing Pipeline] → [Main Tables] → [Analytics]
     ✅              ✅                   MISSING              Exists         Exists
```

### Staging Table Schema (`ProcurementDataStaging`)

- Purchase Order fields: `po_number`, `line_item_number`
- Supplier fields: `supplier_name`, `supplier_code`, `supplier_site`
- Material fields: `material_code`, `material_description`, `material_category`
- Pricing fields: `unit_price`, `total_price`, `currency`
- Date fields: `purchase_date`, `delivery_date`, `invoice_date`

### Main Business Tables (Not Connected)

- `procurement.Supplier` - Supplier master data
- `pricing.Material` - Material catalog
- `pricing.Price` - Time-series pricing (TimescaleDB)
- `procurement.PurchaseOrder` - Purchase orders
- `procurement.RFQ` - Request for quotations

### Analytics Tables (Reads from Main Tables)

- `analytics.DashboardMetric` - KPI calculations
- `analytics.Report` - Generated reports
- `analytics.Alert` - System alerts

## Data Ingestion Module (Phase 0.5 - COMPLETE)

### Supported Formats
- CSV, Excel (XLSX/XLS), Parquet
- 50MB file size limit
- Smart column detection
- Reusable mapping templates

### Upload Workflow
1. Upload file: `POST /data-ingestion/upload/`
2. Map columns: `GET /data-ingestion/mapping/{upload_id}/`
3. Validate: `GET /data-ingestion/validation/{upload_id}/`
4. Process: `POST /data-ingestion/process/{upload_id}/`

### Test Data
```bash
# Create sample procurement data
docker exec -it pricing_django python manage.py create_sample_procurement_data

# Load sample data
docker exec -it pricing_django python manage.py load_sample_data
```

## Django Development Guidelines

### Models
- Use UUID primary keys
- Include `created_at`, `updated_at` timestamps
- Implement soft deletes where appropriate
- Follow pattern in `apps/data_ingestion/models.py`

### Views
- Class-based views for complex logic
- Function-based views for HTMX partials
- Return proper HTMX headers (HX-Trigger, HX-Redirect)
- Check permissions with `@login_required` or permission_classes

### Templates
- Base template: `templates/base.html` (includes HTMX, Alpine.js, Tailwind, logout modal)
- Authentication: `templates/auth/login.html` (styled login with gradient animations)
- Analytics: `templates/analytics/` for analytics center and tab content
- Partials: `templates/partials/` for HTMX fragments
- Components: `templates/components/` for reusable UI
- Navy Blue & White theme (consistent across all pages)

### HTMX Patterns
```html
<!-- Lazy loading -->
<div hx-get="/data" hx-trigger="revealed">Loading...</div>

<!-- Form submission -->
<form hx-post="/submit" hx-target="#result">

<!-- Polling -->
<div hx-get="/status" hx-trigger="every 2s">

<!-- Inline editing -->
<span hx-get="/edit" hx-trigger="click" hx-swap="outerHTML">

<!-- Tab switching (Analytics) -->
<button onclick="switchTab(this, 'insights')" 
        hx-get="/analytics/tab/insights/" 
        hx-target="#tab-content"
        hx-swap="innerHTML">
    Key Insights
</button>

<!-- Modal triggers -->
<button onclick="openDateRangeModal()">Date Range</button>
<button onclick="generateReport()">Generate Report</button>
```

## Database Configuration

### PostgreSQL with TimescaleDB
- Database: `pricing_agent`
- User: `pricing_user`
- Password: `pricing_password`
- Host: `postgres` (in Docker), `localhost` (local)
- Port: `5432`

### Django Models Example
```python
from django.db import models
import uuid

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
```

## Current Implementation Status

### ✅ Phase 1: Price History Recording (COMPLETE)
- **Automated Price Recording**: Historical price tracking from procurement data
- **Time-Series Storage**: PostgreSQL with TimescaleDB integration
- **Material & Supplier Tracking**: Comprehensive catalog management
- **560+ Records Processed**: Successfully tested with real-world data patterns

### ✅ Phase 2: Comprehensive Analytics Suite (COMPLETE)
- **Enhanced Analytics Engine**: Real-time KPI dashboards and metrics
- **Data Quality Scoring**: 6-dimensional quality assessment system
- **Optimized Processing**: 640x performance improvement (32s → 0.05s)
- **Conflict Resolution**: Fuzzy matching with 75-95% similarity thresholds
- **API Endpoints**: RESTful APIs for all analytics features
- **Comprehensive Testing**: All 7 test categories passing

### ✅ Core Features (Fully Operational)
- **Data Upload & Ingestion**: CSV, Excel, Parquet support with smart detection
- **Data Integration Pipeline**: Complete processing from staging to main tables
- **Analytics Dashboard**: Interactive visualizations with Chart.js
- **Fuzzy Matching Engine**: Intelligent deduplication with configurable thresholds
- **Conflict Resolution UI**: Manual review interface for ambiguous matches
- **Authentication System**: Secure login with gradient animations
- **Multi-tenant Architecture**: Organization-level data isolation
- **HTMX Integration**: Dynamic UI updates without full page reloads

### 📊 Performance Metrics
- Processing Speed: 0.05s for 10 records (640x improvement)
- Fuzzy Match Accuracy: 85-95%
- Data Quality Dimensions: 6
- API Response Time: <100ms
- Test Coverage: 100% (All 7 categories)

### 🚀 Next Phase: ML/AI Integration (Q1 2025)
1. **Activate FastAPI ML Service**:
   - Price prediction models
   - Should-cost modeling algorithms
   - Advanced anomaly detection with ML
   - Automated negotiation recommendations

2. **Enterprise Features (Q2 2025)**:
   - WebSocket real-time updates
   - ERP system integration (SAP, Oracle)
   - Supplier portal with collaboration
   - Advanced RBAC with fine-grained permissions

3. **Advanced Analytics (Q3 2025)**:
   - Predictive spend analytics
   - Market intelligence integration
   - Supply chain risk assessment
   - Contract compliance monitoring

## Environment Variables

### Essential for Development
```bash
DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=postgres://pricing_user:pricing_password@postgres:5432/pricing_agent
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mailhog
EMAIL_PORT=1025
```

## Service URLs

- **Django Application**: `http://localhost:8000`
- **Django Admin**: `http://localhost:8000/admin`
- **Login Page**: `http://localhost:8000/accounts/login/`
- **Analytics Dashboard**: `http://localhost:8000/analytics/`
- **Data Upload**: `http://localhost:8000/data-ingestion/upload/`
- **MailHog Email UI**: `http://localhost:8025`
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`
- **FastAPI ML** (when activated): `http://localhost:8001`

## Troubleshooting

### Django Connection Issues
```bash
# Check container status
docker ps

# View Django logs
docker-compose -f docker-compose.simple.yml logs django

# Restart Django
docker-compose -f docker-compose.simple.yml restart django
```

### Missing Python Packages
```bash
# Add to requirements-simple.txt, then:
docker-compose -f docker-compose.simple.yml up -d --build django
```

### Database Issues
```bash
# Reset database
docker exec -it pricing_django python manage.py flush --noinput
docker exec -it pricing_django python manage.py migrate
```

### Static Files Not Loading
```bash
docker exec -it pricing_django python manage.py collectstatic --noinput
```

## Important Files

### Core Documentation
- `PLAN.md` - Detailed implementation roadmap
- `PRICING_ANALYTICS_PLAN.md` - Analytics implementation guide
- `DATA_INTEGRATION_PIPELINE.md` - **CRITICAL** - Requirements for connecting staging data to main tables
- `ANALYTICS_FEATURES.md` - Comprehensive analytics module documentation
- `TESTING.md` - Testing strategy and guidelines
- `WINDOWS_LOCAL_SETUP.md` - Windows-specific development setup

### Configuration Files
- `docker-compose.simple.yml` - Simplified Docker setup (USE THIS)
- `docker-compose.windows.yml` - Windows-specific Docker services (PostgreSQL, Redis, MailHog only)
- `docker-compose.prod.yml` - Production Docker configuration
- `requirements-simple.txt` - Python dependencies
- `Makefile` - Common commands for testing and development
- `.env.production.template` - Production environment template

### Windows Development Scripts
- `start-windows.bat` - Full interactive startup script with Docker and all services
- `stop-windows.bat` - Comprehensive shutdown script with cleanup options
- **Quick Local Testing Scripts**:
  - `install-local.bat` - Install minimal dependencies for local testing
  - `test-django.bat` - Simplest script to just run Django server
  - `start-local.bat` - Local testing with automatic port conflict resolution
  - `start-local.ps1` - PowerShell version with better port detection

### Deployment & Operations
- `DEPLOYMENT_READY.md` - Deployment readiness status
- `DEPLOYMENT_CHECKLIST.md` - Production deployment checklist
- `sample_procurement_data.csv` - Test data for uploads

## Git Workflow

```bash
# Branch naming
feature/TICKET-description
bugfix/TICKET-description

# Commit format
type(scope): subject
# Types: feat, fix, docs, style, refactor, test, chore
```

## Management Commands

```bash
# Create sample data
docker exec -it pricing_django python manage.py create_sample_procurement_data

# Load fixtures
docker exec -it pricing_django python manage.py load_sample_data

# Load test data for procurement module
docker exec -it pricing_django python manage.py load_test_data

# Setup RBAC
docker exec -it pricing_django python manage.py setup_rbac

# Ensure user profiles
docker exec -it pricing_django python manage.py ensure_user_profiles

# Database cleanup for production
docker exec -it pricing_django python manage.py cleanup_database --dry-run --keep-admin
docker exec -it pricing_django python manage.py cleanup_database --keep-admin

# Database backup
docker exec -it pricing_django python manage.py backup_database --format=json
docker exec -it pricing_django python manage.py backup_database --format=sql

# Prepare for deployment
docker exec -it pricing_django python manage.py prepare_deployment

# Health check
docker exec -it pricing_django python manage.py health_check
```

## Testing Strategy

### Unit Tests
```python
# django_app/tests/unit/apps/pricing/test_models.py
from django.test import TestCase
from apps.pricing.models import Material

class MaterialTestCase(TestCase):
    def test_material_creation(self):
        material = Material.objects.create(
            name="Steel Beam",
            unit_price=100.00
        )
        self.assertEqual(material.name, "Steel Beam")
```

### Integration Tests
```python
# django_app/tests/integration/test_api_endpoints.py
from django.test import TestCase, Client

class APITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
    def test_upload_endpoint(self):
        response = self.client.post('/data-ingestion/upload/')
        self.assertEqual(response.status_code, 200)
```

## Performance Optimization

### Database Queries
- Use `select_related()` and `prefetch_related()` to avoid N+1 queries
- Use `only()` to limit fields fetched from database
- Implement bulk operations with `bulk_create()` and `bulk_update()`
- Use database indexes on frequently queried fields

### Data Processing (Optimized)
- **OptimizedDataProcessor**: 640x performance improvement (32s → 0.05s for 10 rows)
- In-memory caching of suppliers, materials, and PO numbers
- Batch processing with configurable batch size (default: 500)
- Fuzzy matching with cached indexes for deduplication
- Bulk database operations instead of individual saves

### Caching Strategy
- Implement Redis caching for frequently accessed data
- Use Django's cache framework: `from django.core.cache import cache`
- Session data optimization (limit to 5 preview rows)
- Cache mapping templates per organization

### Background Processing
- Use `python manage.py process_queue` for large datasets
- Celery integration ready for activation (Week 2)
- Synchronous processing for small datasets (<1000 rows)

## Security Best Practices

- Always use Django's ORM to prevent SQL injection
- Implement CSRF protection (enabled by default)
- Use `@login_required` decorator for protected views
- Validate file uploads (type, size, content)
- Store secrets in environment variables
- Regular dependency updates
- **Logout Security**: POST-only logout to prevent CSRF attacks
- **Authentication Flow**: Proper redirects after login/logout
- **Modal Confirmations**: User confirmation for destructive actions

## Next Implementation Steps

### Phase 3: ML/AI Integration (Q1 2025)
1. **Activate FastAPI ML Service**: Set up the ML sidecar service for advanced analytics
2. **Price Prediction Models**: Implement time-series forecasting with LSTM/Prophet
3. **Should-Cost Modeling**: Build component-based cost analysis algorithms
4. **Advanced Anomaly Detection**: Deploy unsupervised learning for outlier detection
5. **Negotiation Recommendations**: Create AI-driven negotiation strategy suggestions

### Phase 4: Enterprise Features (Q2 2025)
1. **Real-time Updates**: Implement WebSocket support for live price monitoring
2. **ERP Integration**: Build connectors for SAP, Oracle, and Microsoft Dynamics
3. **Supplier Portal**: Create collaborative platform for supplier engagement
4. **Advanced RBAC**: Implement fine-grained role-based access control
5. **Multi-language Support**: Internationalize the platform for global deployment

### Phase 5: Advanced Analytics (Q3 2025)
1. **Predictive Spend Analytics**: Forecast future procurement costs
2. **Market Intelligence**: Integrate external market data sources
3. **Supply Chain Risk**: Assess and monitor supplier risk metrics
4. **Contract Compliance**: Automated contract monitoring and alerts
5. **RFQ Automation**: Generate and manage RFQs automatically

## Browser Compatibility & Known Issues

### Browser Support
- ✅ **Chrome/Edge**: Full support, all features working
- ✅ **Firefox**: Full support (after December 2024 fixes)
- ✅ **Safari**: Full support with minor CSS adjustments
- ⚠️ **Internet Explorer**: Not supported

### Firefox-Specific Fixes (December 2024)
- **Issue**: Loading overlay stuck on form pages
- **Root Cause**: JavaScript scope error with `isFirefox` variable
- **Solution**: Moved browser detection to global scope
- **Files Modified**:
  - `django_app/templates/procurement/rfq_form.html`
  - Added failsafe loading removal with multiple attempts
  - Enhanced `hideLoadingIndicators()` function
- **Test Page**: `/procurement/test-firefox/` for debugging

### Known CSS Compatibility Issues
- **`:has()` selector**: Not supported in older Firefox versions
- **Solution**: JavaScript fallback implementation
- **Grid layouts**: May require explicit `display: grid` in Firefox

## Contact

- **Project Owner**: Ayodele Sasore
- **Repository**: https://github.com/bomino/Pricing-Agent2
- **Status**: Production Ready (Phase 1 & 2 Complete)
- **Version**: 2.1
- **Key Documentation**:
  - `README.md` - Project overview and quick start
  - `PLAN.md` - Detailed implementation roadmap
  - `PRICING_ANALYTICS_PLAN.md` - Analytics strategy
  - `PHASE2_IMPLEMENTATION_SUMMARY.md` - Phase 2 details
  - `docs/API_SPECIFICATION.md` - Complete API reference