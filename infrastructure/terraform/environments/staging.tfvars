# Staging Environment Configuration
environment = "staging"
aws_region  = "us-east-1"

# Network Configuration
allowed_cidr_blocks = [
  "10.0.0.0/8",      # Internal network
  "172.16.0.0/12",   # Private network
  "192.168.0.0/16"   # Local network
]

# EKS Node Group Configuration
node_instance_types     = ["t3.medium", "t3.large"]
node_group_min_size    = 2
node_group_max_size    = 10
node_group_desired_size = 3

# Database Configuration
db_instance_class       = "db.t3.medium"
db_allocated_storage   = 50
db_max_allocated_storage = 200

# Redis Configuration
redis_node_type = "cache.t3.micro"

# Cost Optimization for Staging
enable_spot_instances = true
single_nat_gateway   = true
auto_scaling_max_nodes = 15

# Monitoring Configuration
enable_monitoring = true
monitoring_retention_days = 7

# Security Configuration
enable_waf = false  # Disabled for staging to reduce costs
enable_guardduty = false  # Can be enabled if needed

# Development Configuration
enable_development_access = true

# Backup Configuration
backup_retention_days = 7
enable_cross_region_backup = false

# Performance Configuration
database_performance_insights = false  # Disabled to reduce costs
redis_cluster_mode = false

# Compliance Configuration
enable_encryption_at_rest = true
enable_encryption_in_transit = true
compliance_framework = "SOC2"

# Feature Flags
enable_gpu_nodes = false  # Disabled for staging to reduce costs
enable_fargate = true
enable_service_mesh = false  # Can be enabled for testing

# Domain Configuration
domain_name = "staging.pricing-agent.yourdomain.com"
# certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/staging-cert-id"

# Alerting Configuration
alert_email = "devops-staging@yourdomain.com"
# slack_webhook_url = "https://hooks.slack.com/services/YOUR/STAGING/WEBHOOK"

# ML Configuration
ml_model_storage_size = 50
enable_model_versioning = true

# Local Development Access
local_development_ips = [
  # Add your development team IP addresses here
  # "203.0.113.0/32",  # Example IP
]

# Custom Tags for Staging
custom_tags = {
  Environment = "staging"
  Team        = "platform-engineering"
  Purpose     = "testing"
  CostCenter  = "engineering"
  AutoShutdown = "true"  # Can be used by automation to shut down resources after hours
}