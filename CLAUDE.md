# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Pricing Agent for Manufacturing & Construction Procurement - An enterprise B2B platform that automates cost benchmarking, validates quotes, and generates should-cost models using ML to enable 10-15% cost reduction in procurement operations.

**Status**: Phase 1 & Phase 2 Complete (January 2026)
**Latest Update**: Fixed Analytics charts, replaced hardcoded values with calculated metrics across all views

## Architecture

```
Django (Port 8000) - Primary Application
├── Web Interface (HTMX + Alpine.js + Tailwind)
├── Business Logic & Workflows
├── Authentication & Authorization
├── Admin Panel
└── Database Models (PostgreSQL + TimescaleDB)

FastAPI (Port 8001) - ML Service (Ready for activation)
├── Model Serving
├── Async Calculations
└── WebSocket Support
```

### Data Flow
```
[File Upload] → [Staging Table] → [Processing Pipeline] → [Main Tables] → [Analytics]
      ↓              ↓                    ↓                    ↓              ↓
   CSV/Excel   ProcurementData     DataProcessor        Supplier,      Dashboard,
   Parquet     Staging             Service              Material,      Reports
                                                        Price
```

### Django Apps
- `apps.core` - Base models, RBAC, utilities, notification APIs, dashboard APIs
- `apps.accounts` - User management, profiles
- `apps.data_ingestion` - File upload, column mapping, validation, processing
- `apps.procurement` - Suppliers, RFQs, purchase orders, contracts (calculated stats)
- `apps.pricing` - Materials, price history (TimescaleDB), alerts, price analytics
- `apps.analytics` - Dashboards, KPIs, reports, anomaly detection (calculated metrics)
- `apps.integrations` - External system connectors

## Development Commands

### Quick Start (Local with SQLite)
```bash
cd django_app
python manage.py migrate --settings=pricing_agent.settings_local
python manage.py createsuperuser --settings=pricing_agent.settings_local
python manage.py runserver --settings=pricing_agent.settings_local
```

### Docker (Full Stack with PostgreSQL)
```bash
docker-compose -f docker-compose.simple.yml up -d
docker exec -it pricing_django python manage.py createsuperuser
```

### Running Tests
```bash
# Single test file
cd django_app && python manage.py test apps.data_ingestion.tests --settings=pricing_agent.settings_local

# All Django tests
make test-django

# Specific test categories
make test-unit           # Unit tests only
make test-integration    # Integration tests
pytest -k "test_name"    # Run specific test by name

# With coverage
make coverage-html
```

### Code Quality
```bash
make format      # Black + isort formatting
make lint        # Flake8 + Black check
make type-check  # Mypy type checking
```

### Management Commands
```bash
# Sample data
python manage.py create_sample_procurement_data --settings=pricing_agent.settings_local
python manage.py load_test_data --settings=pricing_agent.settings_local

# Database operations
python manage.py cleanup_database --dry-run --keep-admin
python manage.py backup_database --format=json

# System
python manage.py setup_rbac
python manage.py health_check
```

## Key Patterns

### Models
- UUID primary keys: `id = models.UUIDField(primary_key=True, default=uuid.uuid4)`
- Timestamps: `created_at = models.DateTimeField(auto_now_add=True)`
- Soft deletes where appropriate
- Reference: `apps/data_ingestion/models.py`

### Views - Calculated Data Pattern
All views should calculate values from database rather than using hardcoded values:
```python
# Good - calculate from database
context['total_spend'] = PurchaseOrder.objects.filter(
    organization=organization,
    created_at__year=current_year,
    created_at__month=current_month
).aggregate(total=Sum('total_amount'))['total'] or 0

# Bad - hardcoded
context['total_spend'] = 47500
```

### URL Patterns with UUID
All URL patterns using model primary keys must use `<uuid:pk>` (not `<int:pk>`):
```python
# Correct
path('materials/<uuid:pk>/', views.MaterialDetailView.as_view(), name='material_detail'),

# Incorrect (will cause 404 errors)
path('materials/<int:pk>/', views.MaterialDetailView.as_view(), name='material_detail'),
```

### HTMX Integration
```html
<!-- Lazy loading -->
<div hx-get="/data" hx-trigger="revealed">Loading...</div>

<!-- Form submission -->
<form hx-post="/submit" hx-target="#result">

<!-- Tab switching -->
<button hx-get="/analytics/tab/insights/" hx-target="#tab-content" hx-swap="innerHTML">

<!-- Notification polling -->
<div hx-get="/api/notifications/unread-count/" hx-trigger="every 30s">
```

### Templates
- Base: `templates/base.html` (HTMX, Alpine.js, Tailwind, logout modal)
- Base Modern: `templates/base_modern.html` (enhanced styling)
- Partials: `templates/partials/` for HTMX fragments
- Theme: Navy Blue & White

## Database Configuration

### Local (SQLite)
Use `--settings=pricing_agent.settings_local` for all commands

### Docker (PostgreSQL + TimescaleDB)
```
Database: pricing_agent
User: pricing_user
Password: pricing_password
Host: postgres (Docker) / localhost (local)
Port: 5432
```

## Key URLs

### Main Application
- Dashboard: `/dashboard/`
- Login: `/accounts/login/`
- Data Upload: `/data-ingestion/upload/`
- Analytics: `/analytics/`
- Admin: `/admin/`

### Pricing Module
- Materials List: `/pricing/materials/`
- Material Detail: `/pricing/materials/<uuid:pk>/`
- Material Price History: `/pricing/materials/<uuid:pk>/price-history/`
- All Prices: `/pricing/prices/`

### Procurement Module
- RFQs: `/procurement/rfqs/`
- Suppliers: `/procurement/suppliers/`
- Purchase Orders: `/procurement/purchase-orders/`

### API Endpoints (HTMX)
- Recent RFQs: `/api/dashboard/recent-rfqs/`
- Price Alerts: `/api/dashboard/price-alerts/`
- Notifications: `/api/notifications/`
- Unread Count: `/api/notifications/unread-count/`

## Services

### Data Processing (`apps/data_ingestion/services/`)
- `OptimizedDataProcessor` - 640x performance improvement for bulk processing
- Fuzzy matching with 75-95% similarity thresholds
- Batch processing (default: 500 records)

### Analytics (`apps/analytics/`)
- Data quality scoring (6 dimensions)
- Anomaly detection (z-score based)
- Savings opportunity identification
- Calculated prediction metrics

### Pricing (`apps/pricing/`)
- Price model for time-series price data
- PriceHistory model for tracking price changes
- Calculated statistics (current, avg, min, max prices)

## Environment Variables

```bash
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://pricing_user:pricing_password@postgres:5432/pricing_agent
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
```

## Important Documentation

- `docs/features/DATA_INTEGRATION_PIPELINE.md` - Data processing requirements
- `docs/features/PROCUREMENT_MODULES_IMPLEMENTATION_GUIDE.md` - Procurement module
- `docs/API_SPECIFICATION.md` - API reference
- `PLAN.md` - Implementation roadmap

## Windows Development

Batch scripts available:
- `start-windows.bat` - Full interactive setup
- `test-django.bat` - Quick server start
- `start-local.bat` - Local testing with port resolution

Always add `--settings=pricing_agent.settings_local` when running locally.

## Recent Fixes (January 2026)

### Hardcoded Values Replaced with Calculated Data
- Dashboard MTD spend now calculated from PurchaseOrder model
- Spend trend percentage calculated by comparing current vs previous month
- Analytics predictions tab shows calculated metrics from actual data
- Procurement dashboard shows real supplier/RFQ counts
- Material detail shows calculated price statistics

### Pricing Module Fixes
- Changed all URL patterns from `<int:pk>` to `<uuid:pk>`
- Created MaterialPriceHistoryView with calculated statistics
- Created material_detail.html template with pricing and order metrics
- Fixed PriceListView to query Price model (not empty PriceHistory)
- Created prices_list.html with filtering and calculated stats

### API Endpoints Added
- `/api/notifications/` - Notifications list for header
- `/api/notifications/unread-count/` - Badge count for header
- `/api/notifications/mark-all-read/` - Mark notifications read
- `/api/dashboard/recent-rfqs/` - Recent RFQs for dashboard
- `/api/dashboard/price-alerts/` - Active alerts for dashboard

## Firefox Compatibility

Known issue with loading overlay stuck on form pages. Solution in `django_app/templates/procurement/rfq_form.html` - browser detection moved to global scope with failsafe removal.
