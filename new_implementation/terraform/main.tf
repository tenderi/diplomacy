terraform {
  required_version = ">= 1.3.0"
  backend "s3" {
        bucket = "diplomacy-bot-test-polarsquad"
        key    = "diplomacy-terraform-state"
        region = "eu-west-1"
  }


  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }
}

provider "aws" {
  region = "eu-west-1"
}
# Networking (VPC, subnets, security groups)
module "network" {
  source = "./network"
}

# RDS PostgreSQL
module "rds" {
  source      = "./rds"
  vpc_id      = module.network.vpc_id
  subnet_ids  = module.network.private_subnet_ids
  rds_sg_id   = module.network.rds_sg_id
  db_name     = var.db_name
  db_username = var.db_username
  db_password = var.db_password
}

# ECS Cluster and Fargate Service
module "ecs" {
  source            = "./ecs"
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  ecs_sg_id         = module.network.ecs_sg_id
  app_image         = module.ecr.repository_url
  db_endpoint       = module.rds.endpoint
  db_name           = var.db_name
  db_username       = var.db_username
  db_password       = var.db_password
  telegram_bot_token = var.telegram_bot_token
  target_group_arn  = module.load_balancer.target_group_arn
  aws_region        = var.aws_region
}

# CloudWatch log groups
module "cloudwatch" {
  source = "./cloudwatch"
}

# Optionally, ECR for container images
module "ecr" {
  source = "./ecr"
} 

module "load_balancer" {
  source            = "./load_balancer"
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  ecs_target_port   = 8000
} 