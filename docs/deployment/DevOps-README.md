# AI Pricing Agent - DevOps Infrastructure Guide

This comprehensive guide covers the complete DevOps infrastructure for the AI Pricing Agent system, designed for enterprise-grade deployment with 99.9% uptime and support for 10K+ concurrent users.

## 🏗️ Architecture Overview

The AI Pricing Agent follows a microservices architecture with the following components:

- **Django Application**: Main web application and REST API
- **FastAPI ML Service**: Machine learning inference service with optional GPU support
- **PostgreSQL + TimescaleDB**: Primary database with time-series capabilities
- **Redis**: Caching layer and message broker
- **Celery**: Distributed task processing
- **Kubernetes**: Container orchestration
- **Monitoring Stack**: Prometheus, Grafana, Loki, and Alertmanager

## 📋 Quick Start

### Prerequisites

- Docker and Docker Compose
- Kubernetes cluster (local or cloud)
- Terraform (for infrastructure provisioning)
- kubectl, helm, kustomize
- Python 3.11+ and Poetry

### Local Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd pricing-agent

# Run the automated setup script
./scripts/setup-dev-environment.sh

# Start development environment
./scripts/dev/run-dev-server.sh
```

### Production Deployment

```bash
# Deploy infrastructure with Terraform
cd infrastructure/terraform
terraform init
terraform plan -var-file="environments/production.tfvars"
terraform apply -var-file="environments/production.tfvars"

# Deploy applications to Kubernetes
./scripts/deploy.sh -e production -t v1.0.0
```

## 🐳 Docker Configuration

### Multi-stage Dockerfiles

The project includes optimized multi-stage Dockerfiles:

- **Dockerfile.django**: Production-ready Django application
- **Dockerfile.fastapi**: FastAPI ML service with CPU and GPU variants

#### Key Features:
- Multi-stage builds for optimized image sizes
- Non-root user execution for security
- Health checks and readiness probes
- Security scanning integration
- Layer caching optimization

### Docker Compose

- **docker-compose.yml**: Local development environment
- **docker-compose.prod.yml**: Production-like environment with resource limits

```bash
# Start development environment
docker-compose up -d

# Start production-like environment
docker-compose -f docker-compose.prod.yml up -d
```

## ☸️ Kubernetes Deployment

### Namespace Structure

```
pricing-agent/              # Production namespace
pricing-agent-staging/      # Staging namespace
pricing-agent-monitoring/   # Monitoring stack
```

### Core Components

1. **Application Services**:
   - Django deployment with HPA (3-20 replicas)
   - FastAPI deployment with HPA (2-10 replicas)
   - FastAPI GPU deployment (1-5 replicas)

2. **Data Layer**:
   - PostgreSQL StatefulSet with TimescaleDB
   - Redis deployment with sentinel support
   - Persistent volumes for data persistence

3. **Background Processing**:
   - Celery worker deployments
   - Priority queue workers
   - Beat scheduler for periodic tasks

4. **Networking**:
   - Nginx ingress controller
   - Network policies for security
   - Service mesh ready (Istio/Linkerd)

### Deployment Commands

```bash
# Deploy to staging
kubectl apply -f infrastructure/k8s/ -n pricing-agent-staging

# Deploy to production using the deployment script
./scripts/deploy.sh -e production -t v1.2.3

# Check deployment status
kubectl get pods -n pricing-agent
kubectl rollout status deployment/pricing-django -n pricing-agent
```

## 🚀 CI/CD Pipeline

### GitHub Actions Workflows

1. **CI Pipeline** (`.github/workflows/ci.yml`):
   - Security scanning with Trivy
   - Code quality checks (Black, Ruff, MyPy)
   - Unit and integration tests
   - Docker image building and scanning
   - Performance testing

2. **CD Pipeline** (`.github/workflows/cd.yml`):
   - Blue-green deployment to production
   - Automated rollback on failure
   - Staging environment promotion
   - Release management

3. **Monitoring** (`.github/workflows/monitoring.yml`):
   - Health checks every 15 minutes
   - Performance tests daily
   - Security scans weekly
   - Backup verification

### Pipeline Features

- **Security**: SAST, dependency scanning, container scanning
- **Quality Gates**: Code coverage, linting, type checking
- **Testing**: Unit, integration, performance, and E2E tests
- **Deployment**: Blue-green strategy with automatic rollback
- **Notifications**: Slack integration for all pipeline events

## 🏗️ Infrastructure as Code

### Terraform Configuration

The Terraform configuration provisions complete AWS infrastructure:

```bash
# Initialize Terraform
cd infrastructure/terraform
terraform init

# Plan deployment
terraform plan -var-file="environments/production.tfvars"

# Apply configuration
terraform apply -var-file="environments/production.tfvars"
```

#### Resources Provisioned:

- **Networking**: VPC, subnets, NAT gateways, security groups
- **Compute**: EKS cluster with managed node groups and GPU nodes
- **Storage**: RDS PostgreSQL, ElastiCache Redis, S3 buckets
- **Security**: KMS keys, IAM roles, security groups
- **Monitoring**: CloudWatch logs and metrics

#### Environment Configurations:

- **Staging** (`staging.tfvars`): Cost-optimized setup
- **Production** (`production.tfvars`): High-availability configuration

## 📊 Monitoring and Observability

### Monitoring Stack Components

1. **Prometheus**: Metrics collection and alerting
2. **Grafana**: Dashboards and visualization
3. **Loki + Promtail**: Log aggregation and analysis
4. **Alertmanager**: Alert routing and notifications

### Pre-built Dashboards

- **Overview Dashboard**: System-wide health and performance
- **ML Service Dashboard**: Model performance and prediction metrics
- **Infrastructure Dashboard**: Kubernetes cluster resources

### Alert Rules

- Service availability monitoring
- Performance threshold alerts
- Error rate monitoring
- Resource utilization alerts
- Database and cache health

### Deployment

```bash
# Deploy monitoring stack
kubectl apply -f infrastructure/k8s/monitoring/ -n pricing-agent-monitoring

# Access Grafana
kubectl port-forward svc/grafana 3000:3000 -n pricing-agent-monitoring
# Open http://localhost:3000 (admin/admin123)
```

## 🔧 Operational Scripts

### Deployment Script

```bash
# Deploy to staging
./scripts/deploy.sh -e staging -t latest

# Deploy to production with backup
./scripts/deploy.sh -e production -t v1.2.3

# Rollback deployment
./scripts/deploy.sh -e production --rollback

# Dry run deployment
./scripts/deploy.sh -e staging -t latest --dry-run
```

### Health Monitoring

```bash
# Check application health
python3 scripts/health_monitor.py --url https://pricing-agent.com --environment production

# Generate health report
python3 scripts/health_monitor.py --url https://staging.pricing-agent.com --environment staging --output-format json --output-file health-report.json
```

### Backup Management

```bash
# Create full backup
python3 scripts/backup_manager.py --environment production --operation backup --backup-type all

# Verify backup
python3 scripts/backup_manager.py --environment production --operation verify --backup-location s3://bucket/backup.sql.gz

# List backups
python3 scripts/backup_manager.py --environment production --operation list

# Cleanup old backups
python3 scripts/backup_manager.py --environment production --operation cleanup --retention-days 30
```

## 🛡️ Security Configuration

### Security Features

1. **Container Security**:
   - Non-root containers
   - Read-only root filesystems
   - Security context constraints
   - Image vulnerability scanning

2. **Network Security**:
   - Network policies for micro-segmentation
   - TLS encryption for all communications
   - Ingress with WAF protection
   - Private subnets for databases

3. **Access Control**:
   - RBAC for Kubernetes access
   - IAM roles for AWS resources
   - Service accounts with least privilege
   - Multi-factor authentication

4. **Data Protection**:
   - Encryption at rest (databases, S3)
   - Encryption in transit (TLS/mTLS)
   - Secrets management with Kubernetes secrets
   - Key rotation policies

### Security Scanning

```bash
# Run security scan on containers
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image pricing-agent/django:latest

# Kubernetes security assessment
kube-score score infrastructure/k8s/*.yaml
```

## 🔄 Blue-Green Deployment

### Production Deployment Strategy

The production environment uses blue-green deployment for zero-downtime updates:

1. **Blue Environment**: Currently active production environment
2. **Green Environment**: New version deployment target
3. **Traffic Switch**: Instant traffic redirection via load balancer
4. **Rollback**: Quick reversion by switching back to blue environment

### Deployment Process

```bash
# Automated blue-green deployment
./scripts/deploy.sh -e production -t v1.2.3

# The script automatically:
# 1. Deploys to inactive environment (green)
# 2. Runs health checks
# 3. Switches traffic to new environment
# 4. Monitors for issues
# 5. Scales down old environment
```

## 📈 Scaling Configuration

### Horizontal Pod Autoscaling

```yaml
# Django HPA
minReplicas: 3
maxReplicas: 20
targetCPUUtilizationPercentage: 70
targetMemoryUtilizationPercentage: 80

# FastAPI ML Service HPA
minReplicas: 2
maxReplicas: 10
targetCPUUtilizationPercentage: 70

# Celery Workers HPA
minReplicas: 3
maxReplicas: 15
```

### Vertical Pod Autoscaling

VPA is configured for optimal resource allocation:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

### Cluster Autoscaling

EKS cluster autoscaling configuration:

- **Node Groups**: Auto-scaling from 3 to 20 nodes
- **GPU Nodes**: Separate node group for ML workloads
- **Spot Instances**: Cost optimization for non-critical workloads

## 💾 Backup and Recovery

### Backup Strategy

1. **Database Backups**:
   - Daily automated backups with 30-day retention
   - Cross-region replication for disaster recovery
   - Point-in-time recovery capability

2. **Application Data**:
   - ML model artifacts backup
   - Configuration backups
   - Kubernetes manifest backups

3. **Infrastructure**:
   - Terraform state backup
   - EKS cluster configuration backup

### Recovery Procedures

```bash
# Database recovery from backup
kubectl exec -n pricing-agent deployment/pricing-postgres -- psql -U pricing_user -d pricing_agent < backup.sql

# Full disaster recovery
terraform apply -var-file="environments/production.tfvars"
kubectl apply -f infrastructure/k8s/ -n pricing-agent
```

## 📚 Development Workflow

### Local Development

```bash
# Setup development environment
./scripts/setup-dev-environment.sh --mode full

# Start development servers
./scripts/dev/run-dev-server.sh

# Run tests
./scripts/dev/run-tests.sh

# Code quality checks
./scripts/dev/run-linting.sh
```

### Development Tools

- **VS Code**: Configured with Python, Docker, and Kubernetes extensions
- **Pre-commit Hooks**: Automated code quality checks
- **Database GUIs**: PgAdmin and Redis Commander
- **API Documentation**: Swagger UI for FastAPI, Django REST Framework

### Testing Strategy

1. **Unit Tests**: pytest for both Django and FastAPI
2. **Integration Tests**: Docker Compose test environment
3. **Performance Tests**: Artillery for load testing
4. **Security Tests**: Automated security scanning
5. **E2E Tests**: Playwright for browser automation

## 🚨 Troubleshooting

### Common Issues

1. **Pod Crashes**:
   ```bash
   kubectl logs -f deployment/pricing-django -n pricing-agent
   kubectl describe pod <pod-name> -n pricing-agent
   ```

2. **Database Connection Issues**:
   ```bash
   kubectl exec -it deployment/pricing-postgres -n pricing-agent -- psql -U pricing_user -d pricing_agent
   ```

3. **High Memory Usage**:
   ```bash
   kubectl top pods -n pricing-agent
   kubectl describe hpa pricing-django -n pricing-agent
   ```

4. **Network Issues**:
   ```bash
   kubectl get networkpolicies -n pricing-agent
   kubectl describe ingress pricing-agent-ingress -n pricing-agent
   ```

### Debug Commands

```bash
# Check all resources
kubectl get all -n pricing-agent

# View events
kubectl get events -n pricing-agent --sort-by='.lastTimestamp'

# Check resource usage
kubectl top nodes
kubectl top pods -n pricing-agent

# Network debugging
kubectl exec -it deployment/pricing-django -n pricing-agent -- nslookup pricing-postgres
```

## 📖 Additional Resources

### Documentation

- [Django App Architecture](django_app/README.md)
- [FastAPI ML Service](fastapi_ml/README.md)
- [Database Schema](database_schema.sql)
- [API Documentation](docs/api/)

### External Links

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Prometheus Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Grafana Dashboard Gallery](https://grafana.com/grafana/dashboards/)

## 🤝 Contributing

1. Follow the development workflow outlined above
2. Ensure all tests pass before submitting PRs
3. Update documentation for any infrastructure changes
4. Test in staging environment before production deployment

## 📞 Support

For infrastructure issues and questions:
- **DevOps Team**: devops@yourdomain.com
- **On-call**: Slack #pricing-agent-alerts
- **Documentation**: This README and linked resources

---

*This infrastructure is designed for enterprise production use with high availability, security, and scalability requirements. Regular reviews and updates ensure continued reliability and performance.*