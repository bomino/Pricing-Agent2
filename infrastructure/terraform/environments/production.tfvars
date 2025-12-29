# Production Environment Configuration
environment = "production"
aws_region  = "us-east-1"

# Network Configuration
allowed_cidr_blocks = [
  "10.0.0.0/8",      # Internal corporate network
  "172.16.0.0/12",   # Private network ranges
  "203.0.113.0/24"   # Example: specific office IP range (replace with actual)
]

# EKS Node Group Configuration
node_instance_types     = ["m5.large", "m5.xlarge", "c5.large"]
node_group_min_size    = 3
node_group_max_size    = 50
node_group_desired_size = 6

# Database Configuration - Production sizing
db_instance_class       = "db.r5.xlarge"  # Memory optimized for better performance
db_allocated_storage   = 500
db_max_allocated_storage = 3000

# Redis Configuration - Production sizing
redis_node_type = "cache.r5.large"  # Memory optimized

# High Availability Configuration
single_nat_gateway = false  # Multiple NAT gateways for HA
auto_scaling_max_nodes = 50

# Monitoring Configuration
enable_monitoring = true
monitoring_retention_days = 90  # Longer retention for production

# Security Configuration
enable_waf = true
enable_guardduty = true
enable_vpc_flow_logs = true

# Development Configuration
enable_development_access = false  # No dev access in production

# Backup Configuration
backup_retention_days = 30
enable_cross_region_backup = true
backup_region = "us-west-2"

# Performance Configuration
database_performance_insights = true
redis_cluster_mode = true  # Enable cluster mode for better performance

# Compliance Configuration
enable_encryption_at_rest = true
enable_encryption_in_transit = true
compliance_framework = "SOC2"

# Feature Flags
enable_gpu_nodes = true      # Enable for ML workloads
enable_fargate = true
enable_service_mesh = true  # Enable Istio for production

# Domain Configuration
domain_name = "pricing-agent.yourdomain.com"
# certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/production-cert-id"

# Alerting Configuration
alert_email = "production-alerts@yourdomain.com"
# slack_webhook_url = "https://hooks.slack.com/services/YOUR/PRODUCTION/WEBHOOK"

# ML Configuration
ml_model_storage_size = 500
enable_model_versioning = true

# Container Registry
container_registry = "your-registry.com"

# Cost Optimization (disabled for production reliability)
enable_spot_instances = false

# Custom Tags for Production
custom_tags = {
  Environment     = "production"
  Team           = "platform-engineering"
  Purpose        = "production-workload"
  CostCenter     = "product"
  Compliance     = "SOC2"
  BackupRequired = "true"
  HighAvailability = "true"
  BusinessCritical = "true"
  DataClassification = "confidential"
}

# Network Security - Restrict access to production
local_development_ips = [
  # No development IPs for production
  # All access should go through VPN or bastion
]