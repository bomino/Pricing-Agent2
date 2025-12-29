# Variables for Terraform configuration

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
  default     = "staging"
  
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be either 'staging' or 'production'."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "allowed_cidr_blocks" {
  description = "List of CIDR blocks allowed to access the cluster"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# EKS Node Group Configuration
variable "node_instance_types" {
  description = "List of instance types for EKS node group"
  type        = list(string)
  default     = ["t3.large", "t3.xlarge"]
}

variable "node_group_min_size" {
  description = "Minimum number of nodes in the EKS node group"
  type        = number
  default     = 3
}

variable "node_group_max_size" {
  description = "Maximum number of nodes in the EKS node group"
  type        = number
  default     = 20
}

variable "node_group_desired_size" {
  description = "Desired number of nodes in the EKS node group"
  type        = number
  default     = 5
}

variable "node_group_public_key" {
  description = "Public key for EC2 Key Pair for node group access"
  type        = string
  default     = ""
}

# Database Configuration
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
  
  validation {
    condition = can(regex("^db\\.", var.db_instance_class))
    error_message = "Database instance class must start with 'db.'."
  }
}

variable "db_allocated_storage" {
  description = "Initial allocated storage for RDS instance (GB)"
  type        = number
  default     = 100
  
  validation {
    condition     = var.db_allocated_storage >= 20
    error_message = "Database allocated storage must be at least 20 GB."
  }
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS instance (GB)"
  type        = number
  default     = 1000
  
  validation {
    condition     = var.db_max_allocated_storage >= var.db_allocated_storage
    error_message = "Max allocated storage must be greater than or equal to allocated storage."
  }
}

# Redis Configuration
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.medium"
  
  validation {
    condition = can(regex("^cache\\.", var.redis_node_type))
    error_message = "Redis node type must start with 'cache.'."
  }
}

# Monitoring Configuration
variable "enable_monitoring" {
  description = "Enable enhanced monitoring and logging"
  type        = bool
  default     = true
}

variable "monitoring_retention_days" {
  description = "CloudWatch logs retention in days"
  type        = number
  default     = 30
  
  validation {
    condition = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.monitoring_retention_days)
    error_message = "Monitoring retention days must be a valid CloudWatch Logs retention value."
  }
}

# Domain Configuration
variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "pricing-agent.yourdomain.com"
}

variable "certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS"
  type        = string
  default     = ""
}

# Backup Configuration
variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 30
  
  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 365
    error_message = "Backup retention days must be between 1 and 365."
  }
}

# Auto Scaling Configuration
variable "auto_scaling_enabled" {
  description = "Enable auto scaling for EKS node groups"
  type        = bool
  default     = true
}

variable "auto_scaling_max_nodes" {
  description = "Maximum number of nodes for auto scaling"
  type        = number
  default     = 50
}

# Security Configuration
variable "enable_waf" {
  description = "Enable AWS WAF for the load balancer"
  type        = bool
  default     = true
}

variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs"
  type        = bool
  default     = true
}

variable "enable_guardduty" {
  description = "Enable AWS GuardDuty"
  type        = bool
  default     = true
}

# Cost Optimization
variable "enable_spot_instances" {
  description = "Enable spot instances for non-production environments"
  type        = bool
  default     = false
}

variable "spot_instance_types" {
  description = "Instance types for spot instances"
  type        = list(string)
  default     = ["t3.large", "t3.xlarge", "m5.large", "m5.xlarge"]
}

# Development Configuration
variable "enable_development_access" {
  description = "Enable development access (bastion host, etc.)"
  type        = bool
  default     = false
}

# Disaster Recovery
variable "enable_cross_region_backup" {
  description = "Enable cross-region backup replication"
  type        = bool
  default     = false
}

variable "backup_region" {
  description = "Region for cross-region backup replication"
  type        = string
  default     = "us-west-2"
}

# Container Registry
variable "container_registry" {
  description = "Container registry URL"
  type        = string
  default     = "your-registry.com"
}

# Feature Flags
variable "enable_gpu_nodes" {
  description = "Enable GPU node group for ML workloads"
  type        = bool
  default     = true
}

variable "enable_fargate" {
  description = "Enable AWS Fargate profiles"
  type        = bool
  default     = true
}

variable "enable_service_mesh" {
  description = "Enable service mesh (Istio)"
  type        = bool
  default     = true
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
  
  validation {
    condition = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid IPv4 CIDR block."
  }
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets"
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use a single NAT Gateway for all private subnets"
  type        = bool
  default     = false
}

# Compliance Configuration
variable "enable_encryption_at_rest" {
  description = "Enable encryption at rest for all services"
  type        = bool
  default     = true
}

variable "enable_encryption_in_transit" {
  description = "Enable encryption in transit for all services"
  type        = bool
  default     = true
}

variable "compliance_framework" {
  description = "Compliance framework (SOC2, HIPAA, PCI-DSS)"
  type        = string
  default     = "SOC2"
  
  validation {
    condition = contains(["SOC2", "HIPAA", "PCI-DSS", "GDPR"], var.compliance_framework)
    error_message = "Compliance framework must be one of: SOC2, HIPAA, PCI-DSS, GDPR."
  }
}

# Performance Configuration
variable "database_performance_insights" {
  description = "Enable RDS Performance Insights"
  type        = bool
  default     = true
}

variable "redis_cluster_mode" {
  description = "Enable Redis cluster mode"
  type        = bool
  default     = false
}

# Alerting Configuration
variable "alert_email" {
  description = "Email address for alerts"
  type        = string
  default     = "alerts@yourdomain.com"
  
  validation {
    condition = can(regex("^[\\w\\.-]+@[\\w\\.-]+\\.[a-zA-Z]{2,}$", var.alert_email))
    error_message = "Alert email must be a valid email address."
  }
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  default     = ""
  sensitive   = true
}

# ML Configuration
variable "ml_model_storage_size" {
  description = "Size of ML model storage (GB)"
  type        = number
  default     = 100
}

variable "enable_model_versioning" {
  description = "Enable ML model versioning"
  type        = bool
  default     = true
}

# Local development
variable "local_development_ips" {
  description = "List of IP addresses for local development access"
  type        = list(string)
  default     = []
}

# Custom tags
variable "custom_tags" {
  description = "Custom tags to apply to all resources"
  type        = map(string)
  default     = {}
}