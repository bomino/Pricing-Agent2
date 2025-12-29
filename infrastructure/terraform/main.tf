# Main Terraform configuration for AI Pricing Agent infrastructure
terraform {
  required_version = ">= 1.6"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  
  backend "s3" {
    bucket         = "pricing-agent-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "pricing-agent-terraform-locks"
  }
}

# Local variables
locals {
  name            = "pricing-agent"
  environment     = var.environment
  region          = var.aws_region
  cluster_version = "1.28"
  
  tags = {
    Project     = "AI-Pricing-Agent"
    Environment = var.environment
    Terraform   = "true"
    Owner       = "DevOps-Team"
  }
  
  azs      = slice(data.aws_availability_zones.available.names, 0, 3)
  vpc_cidr = "10.0.0.0/16"
  
  # Calculate subnet CIDRs
  private_subnets = [for i, az in local.azs : cidrsubnet(local.vpc_cidr, 8, i)]
  public_subnets  = [for i, az in local.azs : cidrsubnet(local.vpc_cidr, 8, i + 100)]
  database_subnets = [for i, az in local.azs : cidrsubnet(local.vpc_cidr, 8, i + 200)]
}

# Data sources
data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

data "aws_caller_identity" "current" {}

# AWS Provider
provider "aws" {
  region = local.region
  
  default_tags {
    tags = local.tags
  }
}

# VPC Module
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  
  name = "${local.name}-${local.environment}"
  cidr = local.vpc_cidr
  
  azs              = local.azs
  private_subnets  = local.private_subnets
  public_subnets   = local.public_subnets
  database_subnets = local.database_subnets
  
  enable_nat_gateway     = true
  single_nat_gateway     = var.environment == "staging"
  enable_vpn_gateway     = false
  enable_dns_hostnames   = true
  enable_dns_support     = true
  
  # Database subnet group
  create_database_subnet_group = true
  database_subnet_group_name   = "${local.name}-${local.environment}-db"
  
  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
  flow_log_destination_type            = "cloud-watch-logs"
  
  tags = local.tags
}

# EKS Cluster
module "eks" {
  source = "terraform-aws-modules/eks/aws"
  
  cluster_name    = "${local.name}-${local.environment}"
  cluster_version = local.cluster_version
  
  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnets
  cluster_endpoint_public_access = true
  cluster_endpoint_private_access = true
  
  cluster_endpoint_public_access_cidrs = var.allowed_cidr_blocks
  
  # Encryption at rest
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }
  
  # Logging
  cluster_enabled_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  
  # OIDC Identity provider
  cluster_identity_providers = {
    oidc = {
      identity_provider_config_name = "oidc"
      client_id                     = "sts.amazonaws.com"
      issuer_url                    = "https://oidc.eks.${local.region}.amazonaws.com/id/${module.eks.cluster_id}"
    }
  }
  
  # EKS Managed Node Groups
  eks_managed_node_groups = {
    main = {
      name           = "${local.name}-${local.environment}-main"
      instance_types = var.node_instance_types
      capacity_type  = "ON_DEMAND"
      
      min_size     = var.node_group_min_size
      max_size     = var.node_group_max_size
      desired_size = var.node_group_desired_size
      
      disk_size = 50
      disk_type = "gp3"
      
      remote_access = {
        ec2_ssh_key = aws_key_pair.node_group.key_name
        source_security_group_ids = [aws_security_group.node_group_ssh.id]
      }
      
      k8s_labels = {
        Environment = local.environment
        NodeGroup   = "main"
      }
      
      update_config = {
        max_unavailable_percentage = 25
      }
      
      tags = local.tags
    }
    
    # GPU node group for ML workloads
    gpu = {
      name           = "${local.name}-${local.environment}-gpu"
      instance_types = ["g4dn.xlarge", "g4dn.2xlarge"]
      capacity_type  = "ON_DEMAND"
      
      min_size     = 0
      max_size     = var.environment == "production" ? 5 : 2
      desired_size = var.environment == "production" ? 1 : 0
      
      disk_size = 100
      disk_type = "gp3"
      
      ami_type = "AL2_x86_64_GPU"
      
      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }
      
      k8s_labels = {
        Environment = local.environment
        NodeGroup   = "gpu"
        accelerator = "nvidia-tesla-k80"
      }
      
      tags = local.tags
    }
  }
  
  # Fargate profiles for lightweight workloads
  fargate_profiles = {
    default = {
      name = "${local.name}-${local.environment}-fargate"
      selectors = [
        {
          namespace = "fargate"
        }
      ]
      
      tags = local.tags
    }
  }
  
  # AWS Load Balancer Controller IAM role
  create_aws_load_balancer_controller_service_account = true
  
  # EBS CSI Driver
  cluster_addons = {
    aws-ebs-csi-driver = {
      most_recent = true
    }
    aws-efs-csi-driver = {
      most_recent = true
    }
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
  }
  
  tags = local.tags
}

# RDS PostgreSQL with TimescaleDB
resource "aws_db_subnet_group" "postgres" {
  name       = "${local.name}-${local.environment}-postgres"
  subnet_ids = module.vpc.database_subnets
  
  tags = merge(local.tags, {
    Name = "${local.name}-${local.environment}-postgres-subnet-group"
  })
}

resource "aws_security_group" "rds" {
  name_prefix = "${local.name}-${local.environment}-rds-"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = merge(local.tags, {
    Name = "${local.name}-${local.environment}-rds"
  })
}

resource "aws_db_instance" "postgres" {
  identifier = "${local.name}-${local.environment}-postgres"
  
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.db_instance_class
  
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id           = aws_kms_key.rds.arn
  
  db_name  = "pricing_agent"
  username = "pricing_user"
  password = random_password.db_password.result
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  
  backup_window      = "03:00-04:00"
  backup_retention_period = var.environment == "production" ? 30 : 7
  maintenance_window = "sun:04:00-sun:05:00"
  
  multi_az               = var.environment == "production"
  publicly_accessible    = false
  auto_minor_version_upgrade = true
  
  performance_insights_enabled = var.environment == "production"
  monitoring_interval         = var.environment == "production" ? 60 : 0
  monitoring_role_arn        = var.environment == "production" ? aws_iam_role.rds_monitoring[0].arn : null
  
  deletion_protection      = var.environment == "production"
  delete_automated_backups = var.environment != "production"
  skip_final_snapshot     = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "${local.name}-${local.environment}-final-snapshot" : null
  
  tags = merge(local.tags, {
    Name = "${local.name}-${local.environment}-postgres"
  })
}

# ElastiCache Redis
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name}-${local.environment}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name_prefix = "${local.name}-${local.environment}-redis-"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
  
  tags = merge(local.tags, {
    Name = "${local.name}-${local.environment}-redis"
  })
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name}-${local.environment}-redis"
  description                = "Redis for ${local.name} ${local.environment}"
  
  node_type                  = var.redis_node_type
  port                       = 6379
  parameter_group_name       = "default.redis7"
  
  num_cache_clusters         = var.environment == "production" ? 3 : 2
  automatic_failover_enabled = var.environment == "production"
  multi_az_enabled          = var.environment == "production"
  
  subnet_group_name = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]
  
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                = random_password.redis_password.result
  
  snapshot_retention_limit = var.environment == "production" ? 7 : 1
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "sun:05:00-sun:07:00"
  
  tags = local.tags
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${local.name}-${local.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
  
  enable_deletion_protection = var.environment == "production"
  
  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "alb-logs"
    enabled = true
  }
  
  tags = local.tags
}

resource "aws_security_group" "alb" {
  name_prefix = "${local.name}-${local.environment}-alb-"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = merge(local.tags, {
    Name = "${local.name}-${local.environment}-alb"
  })
}

# S3 Buckets
resource "aws_s3_bucket" "alb_logs" {
  bucket        = "${local.name}-${local.environment}-alb-logs-${random_id.bucket_suffix.hex}"
  force_destroy = var.environment != "production"
  
  tags = local.tags
}

resource "aws_s3_bucket" "backups" {
  bucket        = "${local.name}-${local.environment}-backups-${random_id.bucket_suffix.hex}"
  force_destroy = var.environment != "production"
  
  tags = local.tags
}

resource "aws_s3_bucket" "model_artifacts" {
  bucket        = "${local.name}-${local.environment}-models-${random_id.bucket_suffix.hex}"
  force_destroy = var.environment != "production"
  
  tags = local.tags
}

# KMS Keys
resource "aws_kms_key" "main" {
  description             = "KMS key for ${local.name} ${local.environment}"
  deletion_window_in_days = var.environment == "production" ? 30 : 7
  
  tags = local.tags
}

resource "aws_kms_key" "eks" {
  description             = "EKS Secret Encryption"
  deletion_window_in_days = var.environment == "production" ? 30 : 7
  
  tags = local.tags
}

resource "aws_kms_key" "rds" {
  description             = "RDS Encryption"
  deletion_window_in_days = var.environment == "production" ? 30 : 7
  
  tags = local.tags
}

# Random resources
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "random_password" "redis_password" {
  length  = 32
  special = true
}

# Key pair for node group access
resource "aws_key_pair" "node_group" {
  key_name   = "${local.name}-${local.environment}-node-group"
  public_key = var.node_group_public_key
  
  tags = local.tags
}

resource "aws_security_group" "node_group_ssh" {
  name_prefix = "${local.name}-${local.environment}-node-ssh-"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }
  
  tags = merge(local.tags, {
    Name = "${local.name}-${local.environment}-node-ssh"
  })
}

# RDS Enhanced Monitoring
resource "aws_iam_role" "rds_monitoring" {
  count = var.environment == "production" ? 1 : 0
  name  = "${local.name}-${local.environment}-rds-monitoring"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  count      = var.environment == "production" ? 1 : 0
  role       = aws_iam_role.rds_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}