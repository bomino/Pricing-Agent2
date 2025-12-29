# AI Pricing Agent for Manufacturing & Construction Procurement

An enterprise-grade AI-powered platform that automates cost benchmarking, validates quotes, and generates should-cost models to enable 10-15% cost reduction in procurement operations.

## 🚀 Features

### ✅ Completed
- **📊 Data Upload & Ingestion**: Direct upload of procurement data (CSV, Excel, Parquet) with smart schema detection
- **🎨 Analytics Dashboard**: Modern gradient UI with interactive tabs, date range selection, and report generation
- **🔐 Authentication System**: Secure login/logout with modal confirmations and styled interfaces
- **Multi-tenant Architecture**: Organization-level data isolation and security
- **Admin Panel**: Django admin for data management

### 🚧 In Development (Requires Data Integration Pipeline)
- **⚠️ Data Integration Pipeline**: **CRITICAL GAP** - Uploaded data needs processing pipeline to main tables
- **AI-Powered Price Predictions**: Machine learning models (blocked - needs integrated data)
- **Cost Benchmarking**: Automated comparison (blocked - needs integrated data)
- **Should-Cost Modeling**: Component-based analysis (blocked - needs integrated data)
- **Anomaly Detection**: Real-time identification (blocked - needs integrated data)
- **Supplier Performance Scoring**: Advanced analytics (blocked - needs integrated data)

### 📅 Planned
- **Real-time Updates**: WebSocket support for live price updates
- **Enterprise Integration**: ERP, supplier APIs, and market data integration

## ⚠️ Critical Implementation Note

**The Data Integration Pipeline is NOT implemented**. Uploaded data remains in staging tables and is not available for analytics or ML models. See `DATA_INTEGRATION_PIPELINE.md` for implementation requirements.

### Current Data Flow
```
✅ File Upload → ✅ Staging Table → ❌ [NO PROCESSING] → ❌ [NO ANALYTICS]
```

### Required Data Flow
```
File Upload → Staging Table → Processing Pipeline → Main Tables → Analytics/ML
```

## 🏗️ Architecture

The system uses a Django-centric architecture with a FastAPI ML sidecar service:

```
┌─────────────────────────────────────────┐
│           NGINX (Reverse Proxy)          │
└─────────────┬────────────┬───────────────┘
              │            │
              ▼            ▼
┌──────────────────┐  ┌───────────────────┐
│  Django (8000)   │  │  FastAPI (8001)   │
│  - Web UI (HTMX) │  │  - ML Models      │
│  - Business Logic│  │  - Predictions    │
│  - Admin Panel   │  │  - Analytics      │
└──────────────────┘  └───────────────────┘
              │            │
              ▼            ▼
┌─────────────────────────────────────────┐
│     PostgreSQL + TimescaleDB + Redis    │
└─────────────────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16+ with TimescaleDB extension
- Redis 7.2+
- Node.js 18+ (for frontend tooling)
- Git

## 🛠️ Installation

### Quick Start with Docker (Simplified Setup)

1. **Clone the repository**:
```bash
git clone https://github.com/vstx/pricing-agent.git
cd pricing-agent
```

2. **Start all services using simplified setup**:
```bash
docker-compose -f docker-compose.simple.yml up -d
```

3. **Create superuser** (optional):
```bash
docker exec -it pricing_django python manage.py createsuperuser
```

4. **Access the application**:
- Web UI: http://localhost:8000
- Analytics Dashboard: http://localhost:8000/analytics/
- Admin Panel: http://localhost:8000/admin
- Login Page: http://localhost:8000/accounts/login/
- MailHog Email UI: http://localhost:8025
- API Documentation: http://localhost:8001/docs (pending FastAPI setup)

### Local Development Setup

1. **Install dependencies**:
```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install Python dependencies
poetry install

# Activate virtual environment
poetry shell
```

2. **Set up database**:
```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Run migrations
python django_app/manage.py migrate
```

3. **Start development servers**:
```bash
# Terminal 1: Django
python django_app/manage.py runserver

# Terminal 2: FastAPI
uvicorn fastapi_ml.main:app --reload --port 8001

# Terminal 3: Celery
celery -A pricing_agent worker -l info

# Terminal 4: Celery Beat
celery -A pricing_agent beat -l info
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
make test

# Run specific test categories
make test-unit          # Unit tests only
make test-integration   # Integration tests
make test-e2e          # End-to-end tests
make test-performance  # Performance tests
make test-security     # Security tests

# Generate coverage report
make coverage-html
open htmlcov/index.html
```

## 📊 ML Model Training

Train and deploy ML models:

```bash
# Train price prediction model
python fastapi_ml/services/training_pipeline.py --model price_prediction

# Train all models
make train-models

# Deploy new model version
python scripts/deploy_model.py --model price_prediction --version v2.0
```

## 🚀 Deployment

### Production Deployment with Kubernetes

```bash
# Build and push Docker images
make build-prod
make push-images

# Deploy to Kubernetes
kubectl apply -f infrastructure/k8s/

# Monitor deployment
kubectl get pods -n pricing-agent
kubectl logs -f deployment/django-api -n pricing-agent
```

### Blue-Green Deployment

```bash
# Deploy new version
./scripts/deploy.sh -e production -t v1.2.0 -s blue-green

# Verify deployment
./scripts/health_monitor.py --url https://pricing-agent.com

# Switch traffic
kubectl patch service pricing-agent -p '{"spec":{"selector":{"version":"green"}}}'
```

## 📖 Documentation

- [API Documentation](docs/API.md)
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Security Guidelines](docs/SECURITY.md)
- [Testing Strategy](TESTING.md)
- [Analytics Features](ANALYTICS_FEATURES.md) - NEW: Comprehensive analytics module documentation
- [Development Instructions](CLAUDE.md) - AI assistant guidelines
- [Deployment Checklist](DEPLOYMENT_CHECKLIST.md) - Production deployment steps

## 🔒 Security

This application implements enterprise-grade security:

- **Multi-Factor Authentication (MFA)** with TOTP
- **OAuth2/OIDC** for enterprise SSO
- **Role-Based Access Control (RBAC)**
- **Field-level encryption** for sensitive data
- **GDPR & CCPA compliance**
- **SOC 2 Type II controls**
- **Comprehensive audit logging**

See [Security Documentation](docs/SECURITY.md) for details.

## 📈 Performance

The system is designed to handle:

- **10,000+ concurrent users**
- **<200ms API response time** (p95)
- **<500ms ML prediction latency**
- **99.9% uptime SLA**
- **1000+ batch predictions** in <10 seconds

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is proprietary software. All rights reserved.

## 👥 Team

- **Project Owner**: Ayodele Sasore
- **Technical Lead**: [Your Name]
- **Development Team**: VSTX Engineering

## 📞 Support

For support, email support@pricing-agent.com or create an issue in the repository.

## 🎯 Roadmap

- [x] Phase 0: Project Setup
- [x] **Phase 0.5: Data Ingestion Module** (COMPLETE)
  - [x] Database models for uploads
  - [x] File parser service
  - [x] Schema detection
  - [x] Upload UI with Navy theme
  - [x] Column mapping interface
  - [x] Validation pipeline
- [x] **Phase 0.6: Analytics Dashboard** (v1.1.0 - COMPLETE)
  - [x] Modern gradient UI design
  - [x] Interactive tabbed interface with HTMX
  - [x] Date range selection modal
  - [x] Report generation with multiple formats
  - [x] Real-time metric cards
  - [x] Chart visualization containers
- [ ] Phase 1: Core Foundation
- [ ] Phase 2: Business Domain Implementation
- [ ] Phase 3: ML/AI Implementation
- [ ] Phase 4: Analytics & Reporting
- [ ] Phase 5: Testing & Optimization
- [ ] Phase 6: Production Deployment

See [PLAN.md](PLAN.md) for detailed implementation plan.

## 🙏 Acknowledgments

- Django and FastAPI communities
- HTMX for simplified frontend development
- TimescaleDB for time-series data management
- All open-source contributors

---

**Built with ❤️ by VSTX Team**