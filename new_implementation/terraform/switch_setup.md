# Switching Between Deployment Setups

This document explains how to switch between the single EC2 setup and the full ECS setup.

## Current Setups Available

### 1. Full ECS Setup (`/terraform/`)
- **Cost**: ~$110/month
- **Components**: ECS Fargate, RDS, ALB, NAT Gateway, Bastion
- **Use for**: Production, high availability, auto-scaling

### 2. Single EC2 Setup (`/terraform/single-ec2/`)
- **Cost**: ~$9.50/month (FREE with AWS Free Tier)
- **Components**: Single t3.micro with local PostgreSQL
- **Use for**: Development, testing, small workloads

## Deployment Commands

### Deploy Single EC2 Setup
```bash
cd new_implementation/terraform/single-ec2/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
terraform apply
./deploy_app.sh
```

### Deploy Full ECS Setup
```bash
cd new_implementation/terraform/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
terraform apply
# Deploy via ECS task definition update
```

## Migration Paths

### From Single EC2 to Full ECS
1. **Backup database** from EC2 instance:
   ```bash
   ssh -i ~/.ssh/your-key.pem ec2-user@<ec2-ip>
   sudo -u diplomacy pg_dump -h localhost -U diplomacy diplomacy > backup.sql
   scp -i ~/.ssh/your-key.pem ec2-user@<ec2-ip>:backup.sql ./
   ```

2. **Deploy full ECS setup**:
   ```bash
   cd ../  # Back to main terraform directory
   terraform apply
   ```

3. **Restore database** to RDS:
   ```bash
   # Connect via bastion host and restore
   psql -h <rds-endpoint> -U diplomacy -d diplomacy < backup.sql
   ```

4. **Cleanup single EC2** (optional):
   ```bash
   cd single-ec2/
   terraform destroy
   ```

### From Full ECS to Single EC2
1. **Backup RDS database**:
   ```bash
   # Via bastion host
   pg_dump -h <rds-endpoint> -U diplomacy diplomacy > backup.sql
   ```

2. **Deploy single EC2**:
   ```bash
   cd single-ec2/
   terraform apply
   ./deploy_app.sh
   ```

3. **Restore database** to EC2:
   ```bash
   scp -i ~/.ssh/your-key.pem backup.sql ec2-user@<ec2-ip>:
   ssh -i ~/.ssh/your-key.pem ec2-user@<ec2-ip>
   sudo -u diplomacy psql -h localhost -U diplomacy -d diplomacy < backup.sql
   ```

4. **Cleanup ECS setup** (optional):
   ```bash
   cd ../
   terraform destroy
   ```

## State Management

Both setups use different Terraform state files:
- **Full ECS**: `diplomacy-terraform-state`
- **Single EC2**: `diplomacy-terraform-state-single-ec2`

This means you can safely switch between them without affecting each other's state.

## Cost Optimization Strategy

### Development Workflow
1. **Start with single EC2** for development ($0-9/month)
2. **Test locally** until stable
3. **Migrate to full ECS** for production when needed

### Production Strategy
1. **Single EC2** for small applications (<100 users)
2. **Full ECS** for high availability and scaling needs
3. **Use Reserved Instances** for long-term production (75% savings)

## Resource Name Conflicts

There are **no resource name conflicts** between setups:
- Single EC2 uses `diplomacy-single-*` naming
- Full ECS uses `diplomacy-*` naming

## Quick Reference

| Setup | Directory | State Key | Cost | Use Case |
|-------|-----------|-----------|------|----------|
| Single EC2 | `single-ec2/` | `diplomacy-terraform-state-single-ec2` | $9/month | Dev/Test |
| Full ECS | `./` | `diplomacy-terraform-state` | $110/month | Production | 