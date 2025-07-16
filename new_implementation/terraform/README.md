# Terraform Infrastructure for Diplomacy App on AWS

This folder contains Terraform code to provision and manage the AWS infrastructure required to deploy the Diplomacy server and Telegram bot, as described in ../README_DEPLOY_AWS.md.

## Components Managed
- **VPC, Subnets, Security Groups**: Networking for ECS and RDS
- **RDS (PostgreSQL)**: Managed database for game state
- **ECS Cluster & Fargate Services**: For running the Diplomacy server and Telegram bot
- **IAM Roles & Policies**: For ECS tasks and GitHub Actions
- **ECR (optional)**: If using AWS ECR instead of DockerHub
- **CloudWatch Log Groups**: For ECS task/service logs
- **Load Balancer (optional)**: For public access to the API

## Usage
- Edit the Terraform files to match your AWS account and deployment needs.
- Run `terraform init`, `terraform plan`, and `terraform apply` to provision resources.
- See ../README_DEPLOY_AWS.md for environment variable and deployment details. 