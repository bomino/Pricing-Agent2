# Output values for the Terraform configuration

# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "The CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnets" {
  description = "List of IDs of private subnets"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "List of IDs of public subnets"
  value       = module.vpc.public_subnets
}

output "database_subnets" {
  description = "List of IDs of database subnets"
  value       = module.vpc.database_subnets
}

# EKS Cluster Outputs
output "cluster_id" {
  description = "EKS cluster ID"
  value       = module.eks.cluster_id
}

output "cluster_arn" {
  description = "The Amazon Resource Name (ARN) of the cluster"
  value       = module.eks.cluster_arn
}

output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "The Kubernetes version for the EKS cluster"
  value       = module.eks.cluster_version
}

output "cluster_security_group_id" {
  description = "Security group ids attached to the cluster control plane"
  value       = module.eks.cluster_security_group_id
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "cluster_oidc_issuer_url" {
  description = "The URL on the EKS cluster for the OpenID Connect identity provider"
  value       = module.eks.cluster_oidc_issuer_url
}

output "node_security_group_id" {
  description = "ID of the node shared security group"
  value       = module.eks.node_security_group_id
}

output "eks_managed_node_groups" {
  description = "Map of attribute maps for all EKS managed node groups created"
  value       = module.eks.eks_managed_node_groups
  sensitive   = true
}

# Database Outputs
output "db_instance_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "db_instance_id" {
  description = "RDS instance ID"
  value       = aws_db_instance.postgres.id
}

output "db_instance_address" {
  description = "RDS instance hostname"
  value       = aws_db_instance.postgres.address
}

output "db_instance_port" {
  description = "RDS instance port"
  value       = aws_db_instance.postgres.port
}

output "db_subnet_group_id" {
  description = "RDS subnet group name"
  value       = aws_db_subnet_group.postgres.id
}

output "database_url" {
  description = "Database connection URL (without password)"
  value       = "postgres://pricing_user:PASSWORD@${aws_db_instance.postgres.endpoint}/pricing_agent"
  sensitive   = true
}

# Redis Outputs
output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  description = "Redis cluster port"
  value       = aws_elasticache_replication_group.redis.port
}

output "redis_auth_token" {
  description = "Redis auth token"
  value       = aws_elasticache_replication_group.redis.auth_token
  sensitive   = true
}

# Load Balancer Outputs
output "load_balancer_arn" {
  description = "ARN of the load balancer"
  value       = aws_lb.main.arn
}

output "load_balancer_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "load_balancer_zone_id" {
  description = "Zone ID of the load balancer"
  value       = aws_lb.main.zone_id
}

# S3 Bucket Outputs
output "s3_bucket_alb_logs" {
  description = "S3 bucket for ALB logs"
  value       = aws_s3_bucket.alb_logs.bucket
}

output "s3_bucket_backups" {
  description = "S3 bucket for backups"
  value       = aws_s3_bucket.backups.bucket
}

output "s3_bucket_model_artifacts" {
  description = "S3 bucket for ML model artifacts"
  value       = aws_s3_bucket.model_artifacts.bucket
}

# KMS Key Outputs
output "kms_key_id" {
  description = "KMS Key ID"
  value       = aws_kms_key.main.key_id
}

output "kms_key_arn" {
  description = "KMS Key ARN"
  value       = aws_kms_key.main.arn
}

output "eks_kms_key_arn" {
  description = "EKS KMS Key ARN"
  value       = aws_kms_key.eks.arn
}

output "rds_kms_key_arn" {
  description = "RDS KMS Key ARN"
  value       = aws_kms_key.rds.arn
}

# Security Group Outputs
output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = aws_security_group.rds.id
}

output "redis_security_group_id" {
  description = "ID of the Redis security group"
  value       = aws_security_group.redis.id
}

output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = aws_security_group.alb.id
}

# Sensitive Outputs (for secrets management)
output "db_password" {
  description = "Database password"
  value       = random_password.db_password.result
  sensitive   = true
}

output "redis_password" {
  description = "Redis password"
  value       = random_password.redis_password.result
  sensitive   = true
}

# kubectl configuration
output "kubectl_config" {
  description = "kubectl config as generated by the module."
  value = {
    cluster_name             = module.eks.cluster_id
    endpoint                = module.eks.cluster_endpoint
    region                  = var.aws_region
    certificate_authority   = module.eks.cluster_certificate_authority_data
    token_command          = "aws eks get-token --cluster-name ${module.eks.cluster_id} --region ${var.aws_region}"
  }
  sensitive = true
}

# Environment-specific outputs
output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "region" {
  description = "AWS region"
  value       = var.aws_region
}

# Networking outputs for reference
output "availability_zones" {
  description = "List of availability zones"
  value       = local.azs
}

output "nat_gateway_ids" {
  description = "List of NAT Gateway IDs"
  value       = module.vpc.natgw_ids
}

# Monitoring outputs
output "cloudwatch_log_groups" {
  description = "CloudWatch log groups created"
  value = {
    eks_cluster = "/aws/eks/${module.eks.cluster_id}/cluster"
    vpc_flow_logs = module.vpc.vpc_flow_log_cloudwatch_log_group_name
  }
}

# Tags output for reference
output "common_tags" {
  description = "Common tags applied to all resources"
  value       = local.tags
}

# Connection information for applications
output "connection_info" {
  description = "Connection information for applications"
  value = {
    database = {
      host     = aws_db_instance.postgres.address
      port     = aws_db_instance.postgres.port
      database = aws_db_instance.postgres.db_name
      username = aws_db_instance.postgres.username
    }
    redis = {
      host = aws_elasticache_replication_group.redis.primary_endpoint_address
      port = aws_elasticache_replication_group.redis.port
    }
    kubernetes = {
      cluster_name = module.eks.cluster_id
      endpoint    = module.eks.cluster_endpoint
      region      = var.aws_region
    }
    load_balancer = {
      dns_name = aws_lb.main.dns_name
      zone_id  = aws_lb.main.zone_id
    }
  }
  sensitive = true
}

# Cost tracking outputs
output "resource_counts" {
  description = "Count of major resources created"
  value = {
    vpc_count                = 1
    subnets_count           = length(module.vpc.private_subnets) + length(module.vpc.public_subnets) + length(module.vpc.database_subnets)
    eks_node_groups         = length(module.eks.eks_managed_node_groups)
    rds_instances          = 1
    redis_clusters         = 1
    s3_buckets            = 3
    security_groups       = 4
    kms_keys             = 3
    load_balancers       = 1
  }
}

# Compliance outputs
output "compliance_info" {
  description = "Compliance-related information"
  value = {
    encryption_at_rest = {
      rds_encrypted    = aws_db_instance.postgres.storage_encrypted
      redis_encrypted  = aws_elasticache_replication_group.redis.at_rest_encryption_enabled
      eks_encrypted    = true
    }
    encryption_in_transit = {
      redis_encrypted = aws_elasticache_replication_group.redis.transit_encryption_enabled
      alb_https       = true
    }
    backup_enabled = {
      rds_backup_retention = aws_db_instance.postgres.backup_retention_period
      redis_snapshots     = aws_elasticache_replication_group.redis.snapshot_retention_limit
    }
    monitoring_enabled = {
      vpc_flow_logs        = module.vpc.vpc_flow_log_id != null
      rds_monitoring      = aws_db_instance.postgres.monitoring_interval > 0
      eks_logging         = length(module.eks.cluster_enabled_log_types) > 0
    }
  }
}