#!/bin/bash

set -euo pipefail

# Pricing Agent Deployment Script
# This script handles deployment to staging and production environments

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
KUSTOMIZE_VERSION="5.0.3"
KUBECTL_VERSION="1.28.0"
HELM_VERSION="3.12.0"

# Default values
ENVIRONMENT=""
NAMESPACE=""
IMAGE_TAG=""
DRY_RUN=false
SKIP_TESTS=false
FORCE_DEPLOY=false
ROLLBACK=false
BACKUP_BEFORE_DEPLOY=true

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" >&2
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Help function
show_help() {
    cat << EOF
Pricing Agent Deployment Script

Usage: $0 [OPTIONS]

OPTIONS:
    -e, --environment ENVIRONMENT    Target environment (staging|production)
    -n, --namespace NAMESPACE        Kubernetes namespace (optional, auto-detected from environment)
    -t, --tag IMAGE_TAG             Docker image tag to deploy
    -d, --dry-run                   Perform a dry run without actually deploying
    -s, --skip-tests                Skip pre-deployment tests
    -f, --force                     Force deployment even if validation fails
    -r, --rollback                  Rollback to previous deployment
    --no-backup                     Skip database backup before production deployment
    -h, --help                      Show this help message

EXAMPLES:
    # Deploy to staging with latest tag
    $0 -e staging -t latest

    # Deploy to production with specific version
    $0 -e production -t v1.2.3

    # Dry run deployment to see what would be deployed
    $0 -e staging -t latest --dry-run

    # Rollback production to previous version
    $0 -e production --rollback

    # Force deployment skipping validation
    $0 -e staging -t latest --force --skip-tests

ENVIRONMENT VARIABLES:
    DOCKER_REGISTRY         Docker registry URL (default: your-registry.com)
    KUBECONFIG             Path to kubeconfig file
    SLACK_WEBHOOK_URL      Slack webhook for notifications
    DATABASE_BACKUP_S3     S3 bucket for database backups
EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -s|--skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            -f|--force)
                FORCE_DEPLOY=true
                shift
                ;;
            -r|--rollback)
                ROLLBACK=true
                shift
                ;;
            --no-backup)
                BACKUP_BEFORE_DEPLOY=false
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
    done
}

# Validate arguments
validate_args() {
    if [[ -z "$ENVIRONMENT" ]]; then
        error "Environment is required. Use -e staging or -e production"
    fi

    if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
        error "Environment must be either 'staging' or 'production'"
    fi

    if [[ "$ROLLBACK" == "true" ]]; then
        log "Rollback mode enabled, skipping image tag validation"
        return
    fi

    if [[ -z "$IMAGE_TAG" ]]; then
        error "Image tag is required. Use -t to specify the tag"
    fi

    # Set namespace based on environment if not provided
    if [[ -z "$NAMESPACE" ]]; then
        if [[ "$ENVIRONMENT" == "staging" ]]; then
            NAMESPACE="pricing-agent-staging"
        else
            NAMESPACE="pricing-agent"
        fi
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if kubectl is installed and configured
    if ! command -v kubectl &> /dev/null; then
        error "kubectl is not installed or not in PATH"
    fi

    # Check kubernetes connection
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster. Check your kubeconfig"
    fi

    # Check if kustomize is available
    if ! command -v kustomize &> /dev/null; then
        warn "kustomize not found, installing..."
        install_kustomize
    fi

    # Check if helm is available (for production deployments)
    if [[ "$ENVIRONMENT" == "production" ]] && ! command -v helm &> /dev/null; then
        warn "helm not found, installing..."
        install_helm
    fi

    # Verify namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log "Creating namespace: $NAMESPACE"
        kubectl create namespace "$NAMESPACE"
    fi
}

# Install kustomize
install_kustomize() {
    local temp_dir=$(mktemp -d)
    curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash -s -- "$KUSTOMIZE_VERSION" "$temp_dir"
    sudo mv "$temp_dir/kustomize" /usr/local/bin/
    rm -rf "$temp_dir"
    log "Kustomize $KUSTOMIZE_VERSION installed"
}

# Install helm
install_helm() {
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    chmod 700 get_helm.sh
    ./get_helm.sh --version v$HELM_VERSION
    rm get_helm.sh
    log "Helm $HELM_VERSION installed"
}

# Run pre-deployment tests
run_pre_deployment_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        warn "Skipping pre-deployment tests as requested"
        return
    fi

    log "Running pre-deployment tests..."

    # Check if images exist in registry
    check_image_availability

    # Validate Kubernetes manifests
    validate_manifests

    # Run smoke tests against staging (for production deployments)
    if [[ "$ENVIRONMENT" == "production" ]]; then
        run_staging_smoke_tests
    fi

    log "Pre-deployment tests completed successfully"
}

# Check if Docker images are available
check_image_availability() {
    local registry=${DOCKER_REGISTRY:-"your-registry.com"}
    
    log "Checking image availability..."
    
    # Check Django image
    local django_image="$registry/pricing-agent/django:$IMAGE_TAG"
    if ! docker manifest inspect "$django_image" &> /dev/null; then
        if [[ "$FORCE_DEPLOY" == "false" ]]; then
            error "Django image not found: $django_image"
        else
            warn "Django image not found but force deploy is enabled"
        fi
    fi

    # Check FastAPI image
    local fastapi_image="$registry/pricing-agent/fastapi:$IMAGE_TAG"
    if ! docker manifest inspect "$fastapi_image" &> /dev/null; then
        if [[ "$FORCE_DEPLOY" == "false" ]]; then
            error "FastAPI image not found: $fastapi_image"
        else
            warn "FastAPI image not found but force deploy is enabled"
        fi
    fi

    log "Image availability check completed"
}

# Validate Kubernetes manifests
validate_manifests() {
    log "Validating Kubernetes manifests..."

    local manifests_dir="$PROJECT_ROOT/infrastructure/k8s"
    
    # Use kubeval to validate manifests
    if command -v kubeval &> /dev/null; then
        find "$manifests_dir" -name "*.yaml" -exec kubeval {} \;
    else
        # Fallback to kubectl dry-run
        kubectl apply --dry-run=client -f "$manifests_dir" -R
    fi

    log "Manifest validation completed"
}

# Run smoke tests against staging environment
run_staging_smoke_tests() {
    log "Running smoke tests against staging environment..."

    local staging_url="https://staging.pricing-agent.yourdomain.com"
    
    # Basic health check
    if ! curl -f "$staging_url/health/" &> /dev/null; then
        if [[ "$FORCE_DEPLOY" == "false" ]]; then
            error "Staging environment health check failed"
        else
            warn "Staging health check failed but force deploy is enabled"
        fi
    fi

    # Run comprehensive smoke tests
    if [[ -f "$SCRIPT_DIR/smoke_tests.py" ]]; then
        python3 "$SCRIPT_DIR/smoke_tests.py" --url "$staging_url" --environment staging
    fi

    log "Staging smoke tests completed"
}

# Create database backup before production deployment
create_database_backup() {
    if [[ "$ENVIRONMENT" != "production" || "$BACKUP_BEFORE_DEPLOY" == "false" ]]; then
        return
    fi

    log "Creating database backup before deployment..."

    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_name="pricing-agent-backup-$timestamp"

    # Create backup using kubectl exec
    kubectl exec -n "$NAMESPACE" deployment/pricing-postgres -- \
        pg_dump -U pricing_user pricing_agent | \
        gzip > "$backup_name.sql.gz"

    # Upload to S3 if configured
    if [[ -n "${DATABASE_BACKUP_S3:-}" ]]; then
        aws s3 cp "$backup_name.sql.gz" "s3://$DATABASE_BACKUP_S3/database-backups/"
        rm "$backup_name.sql.gz"
        log "Database backup uploaded to S3: $backup_name.sql.gz"
    else
        log "Database backup created locally: $backup_name.sql.gz"
    fi
}

# Deploy to staging environment
deploy_staging() {
    log "Deploying to staging environment..."

    local manifests_dir="$PROJECT_ROOT/infrastructure/k8s"
    local registry=${DOCKER_REGISTRY:-"your-registry.com"}

    # Apply base manifests
    kubectl apply -f "$manifests_dir/namespace.yaml"
    kubectl apply -f "$manifests_dir/configmaps.yaml" -n "$NAMESPACE"
    kubectl apply -f "$manifests_dir/secrets.yaml" -n "$NAMESPACE"

    # Deploy infrastructure components
    kubectl apply -f "$manifests_dir/postgres.yaml" -n "$NAMESPACE"
    kubectl apply -f "$manifests_dir/redis.yaml" -n "$NAMESPACE"

    # Wait for databases to be ready
    kubectl wait --for=condition=ready pod -l component=postgres -n "$NAMESPACE" --timeout=300s
    kubectl wait --for=condition=ready pod -l component=redis -n "$NAMESPACE" --timeout=300s

    # Update image tags in manifests
    update_image_tags "$manifests_dir" "$registry" "$IMAGE_TAG"

    # Deploy application services
    kubectl apply -f "$manifests_dir/django.yaml" -n "$NAMESPACE"
    kubectl apply -f "$manifests_dir/fastapi.yaml" -n "$NAMESPACE"
    kubectl apply -f "$manifests_dir/celery.yaml" -n "$NAMESPACE"

    # Wait for deployments to be ready
    kubectl rollout status deployment/pricing-django -n "$NAMESPACE" --timeout=600s
    kubectl rollout status deployment/pricing-fastapi -n "$NAMESPACE" --timeout=600s
    kubectl rollout status deployment/pricing-celery-worker -n "$NAMESPACE" --timeout=600s

    log "Staging deployment completed successfully"
}

# Deploy to production environment using blue-green strategy
deploy_production() {
    log "Deploying to production environment using blue-green strategy..."

    local manifests_dir="$PROJECT_ROOT/infrastructure/k8s"
    local registry=${DOCKER_REGISTRY:-"your-registry.com"}

    # Determine current and target environments
    local current_env=$(kubectl get service pricing-agent-active -n "$NAMESPACE" -o jsonpath='{.spec.selector.version}' 2>/dev/null || echo "blue")
    local target_env=$([ "$current_env" = "blue" ] && echo "green" || echo "blue")

    log "Current environment: $current_env, Target environment: $target_env"

    # Deploy to target environment using Helm
    helm upgrade --install "pricing-agent-$target_env" "$PROJECT_ROOT/helm/pricing-agent" \
        --namespace "$NAMESPACE" \
        --values "$PROJECT_ROOT/helm/pricing-agent/values-production.yaml" \
        --set image.django.tag="$IMAGE_TAG" \
        --set image.fastapi.tag="$IMAGE_TAG" \
        --set deployment.version="$target_env" \
        --wait --timeout=10m

    # Run health checks on new deployment
    run_production_health_checks "$target_env"

    # Switch traffic to new deployment
    switch_production_traffic "$target_env"

    # Scale down old deployment after successful switch
    scale_down_old_deployment "$current_env"

    log "Production blue-green deployment completed successfully"
}

# Update image tags in Kubernetes manifests
update_image_tags() {
    local manifests_dir="$1"
    local registry="$2"
    local tag="$3"

    # Use sed to replace image tags (basic implementation)
    # In production, consider using kustomize or helm for better templating
    find "$manifests_dir" -name "*.yaml" -type f -exec sed -i.bak \
        -e "s|image: $registry/pricing-agent/django:.*|image: $registry/pricing-agent/django:$tag|g" \
        -e "s|image: $registry/pricing-agent/fastapi:.*|image: $registry/pricing-agent/fastapi:$tag|g" \
        {} \;

    # Clean up backup files
    find "$manifests_dir" -name "*.yaml.bak" -delete
}

# Run health checks on production deployment
run_production_health_checks() {
    local target_env="$1"
    
    log "Running health checks on production deployment ($target_env)..."

    # Port forward to test the new deployment directly
    kubectl port-forward "service/pricing-django-$target_env" 8080:8000 -n "$NAMESPACE" &
    local pf_pid=$!
    sleep 10

    # Run health checks
    if ! curl -f "http://localhost:8080/health/" &> /dev/null; then
        kill $pf_pid 2>/dev/null || true
        error "Health check failed for new production deployment"
    fi

    # Run comprehensive health checks
    if [[ -f "$SCRIPT_DIR/production_health_check.py" ]]; then
        if ! python3 "$SCRIPT_DIR/production_health_check.py" --url "http://localhost:8080"; then
            kill $pf_pid 2>/dev/null || true
            error "Comprehensive health check failed"
        fi
    fi

    kill $pf_pid 2>/dev/null || true
    log "Health checks passed"
}

# Switch production traffic to new deployment
switch_production_traffic() {
    local target_env="$1"
    
    log "Switching production traffic to $target_env environment..."

    # Update the active service to point to the new deployment
    kubectl patch service pricing-agent-active -n "$NAMESPACE" -p \
        "{\"spec\":{\"selector\":{\"version\":\"$target_env\"}}}"

    # Wait and verify the switch
    sleep 30
    if ! curl -f "https://pricing-agent.yourdomain.com/health/" &> /dev/null; then
        error "Traffic switch verification failed"
    fi

    log "Traffic successfully switched to $target_env"
}

# Scale down old deployment
scale_down_old_deployment() {
    local old_env="$1"
    
    log "Scaling down old deployment ($old_env) in 5 minutes..."
    
    # Wait 5 minutes before scaling down to ensure stability
    sleep 300
    
    kubectl scale deployment "pricing-django-$old_env" --replicas=0 -n "$NAMESPACE"
    kubectl scale deployment "pricing-fastapi-$old_env" --replicas=0 -n "$NAMESPACE"
    kubectl scale deployment "pricing-celery-worker-$old_env" --replicas=0 -n "$NAMESPACE"

    log "Old deployment scaled down"
}

# Rollback deployment
rollback_deployment() {
    log "Rolling back deployment in $ENVIRONMENT..."

    if [[ "$ENVIRONMENT" == "staging" ]]; then
        # For staging, rollback using kubectl
        kubectl rollout undo deployment/pricing-django -n "$NAMESPACE"
        kubectl rollout undo deployment/pricing-fastapi -n "$NAMESPACE"
        kubectl rollout undo deployment/pricing-celery-worker -n "$NAMESPACE"
        
        kubectl rollout status deployment/pricing-django -n "$NAMESPACE"
        kubectl rollout status deployment/pricing-fastapi -n "$NAMESPACE"
        kubectl rollout status deployment/pricing-celery-worker -n "$NAMESPACE"
    else
        # For production, switch back to previous blue-green environment
        local current_env=$(kubectl get service pricing-agent-active -n "$NAMESPACE" -o jsonpath='{.spec.selector.version}')
        local rollback_env=$([ "$current_env" = "blue" ] && echo "green" || echo "blue")
        
        log "Rolling back from $current_env to $rollback_env"
        
        # Scale up rollback environment
        kubectl scale deployment "pricing-django-$rollback_env" --replicas=3 -n "$NAMESPACE"
        kubectl scale deployment "pricing-fastapi-$rollback_env" --replicas=2 -n "$NAMESPACE"
        kubectl scale deployment "pricing-celery-worker-$rollback_env" --replicas=3 -n "$NAMESPACE"
        
        # Wait for rollback deployment to be ready
        kubectl rollout status deployment "pricing-django-$rollback_env" -n "$NAMESPACE" --timeout=300s
        
        # Switch traffic
        switch_production_traffic "$rollback_env"
    fi

    log "Rollback completed successfully"
}

# Send deployment notification
send_notification() {
    local status="$1"
    local message="$2"
    
    if [[ -z "${SLACK_WEBHOOK_URL:-}" ]]; then
        return
    fi

    local color="good"
    if [[ "$status" != "success" ]]; then
        color="danger"
    fi

    local payload=$(cat <<EOF
{
    "attachments": [{
        "color": "$color",
        "title": "Pricing Agent Deployment $status",
        "fields": [
            {"title": "Environment", "value": "$ENVIRONMENT", "short": true},
            {"title": "Image Tag", "value": "${IMAGE_TAG:-"N/A"}", "short": true},
            {"title": "Namespace", "value": "$NAMESPACE", "short": true},
            {"title": "Status", "value": "$message", "short": false}
        ],
        "footer": "Deployment Script",
        "ts": $(date +%s)
    }]
}
EOF
    )

    curl -X POST -H 'Content-type: application/json' \
        --data "$payload" \
        "$SLACK_WEBHOOK_URL" &> /dev/null || true
}

# Main deployment function
main() {
    log "Starting Pricing Agent deployment..."
    
    parse_args "$@"
    validate_args
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN MODE - No actual changes will be made"
    fi

    check_prerequisites
    
    if [[ "$ROLLBACK" == "true" ]]; then
        rollback_deployment
        send_notification "success" "Rollback completed successfully"
        log "Deployment script completed successfully"
        return
    fi

    run_pre_deployment_tests
    create_database_backup

    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would deploy $IMAGE_TAG to $ENVIRONMENT environment"
        return
    fi

    # Deploy based on environment
    if [[ "$ENVIRONMENT" == "staging" ]]; then
        deploy_staging
    else
        deploy_production
    fi

    # Post-deployment verification
    log "Running post-deployment verification..."
    sleep 30
    
    local app_url
    if [[ "$ENVIRONMENT" == "staging" ]]; then
        app_url="https://staging.pricing-agent.yourdomain.com"
    else
        app_url="https://pricing-agent.yourdomain.com"
    fi

    if curl -f "$app_url/health/" &> /dev/null; then
        send_notification "success" "Deployment completed successfully"
        log "Deployment completed successfully!"
    else
        send_notification "failure" "Post-deployment verification failed"
        error "Post-deployment verification failed"
    fi
}

# Trap to handle script interruption
trap 'error "Script interrupted"' INT TERM

# Run main function with all arguments
main "$@"