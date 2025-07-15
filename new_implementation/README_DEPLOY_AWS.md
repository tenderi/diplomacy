# AWS ECS Deployment Guide for Diplomacy App

This guide explains how to deploy the Diplomacy server and Telegram bot to AWS using ECS (Fargate), DockerHub, and GitHub Actions.

---

## Prerequisites
- AWS account with permissions for ECS, ECR, RDS, IAM
- DockerHub account (or use ECR, see below)
- GitHub repository with this codebase

---

## 1. Set Up AWS RDS (Postgres)
1. Go to the [RDS Console](https://console.aws.amazon.com/rds/).
2. Create a new PostgreSQL instance:
   - Username: `diplomacy`
   - Password: `diplomacy` (or your choice)
   - Database: `diplomacy`
   - Make note of the endpoint (e.g., `mydb.abc123xyz.us-west-2.rds.amazonaws.com`).
3. Ensure the security group allows inbound connections from ECS (or 0.0.0.0/0 for testing).

---

## 2. Set Up ECS Cluster & Service
1. Go to the [ECS Console](https://console.aws.amazon.com/ecs/).
2. Create a new **Fargate** cluster.
3. Create a new **Task Definition**:
   - Use the sample `ecs-task-definition.json` in this repo.
   - Set the image to `DOCKERHUB_USERNAME/diplomacy:latest` (replace with your DockerHub username).
   - Set environment variables:
     - `SQLALCHEMY_DATABASE_URL`: `postgresql+psycopg2://diplomacy:diplomacy@YOUR_RDS_ENDPOINT:5432/diplomacy`
     - `TELEGRAM_BOT_TOKEN`: your bot token
     - `DIPLOMACY_API_URL`: `http://localhost:8000`
   - Set port mapping: 8000 TCP
   - Set log group/region as desired
4. Create a **Service** using this task definition.
5. Set up a load balancer or public IP as needed.

---

## 3. Configure GitHub Secrets
In your GitHub repo, go to **Settings > Secrets and variables > Actions** and add:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `TELEGRAM_BOT_TOKEN`

---

## 4. GitHub Actions Pipeline
- The workflow in `.github/workflows/deploy.yml` will:
  1. Build and test your app
  2. Push the Docker image to DockerHub
  3. Update the ECS task definition and deploy the new version
- Edit `ecs-task-definition.json` as needed (see above)
- Edit the ECS job in the workflow to use your cluster/service names

---

## 5. Deploy
- Push to `main` to trigger the pipeline and deploy automatically.
- Monitor the Actions tab and ECS Console for progress.

---

## Troubleshooting
- Check ECS task logs in CloudWatch for errors
- Ensure RDS is accessible from ECS (security group, VPC)
- Ensure DockerHub rate limits are not exceeded
- If using ECR instead of DockerHub, update the workflow and task definition accordingly

---

## References
- [AWS ECS Getting Started](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/getting-started-ecs.html)
- [AWS RDS Docs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html)
- [GitHub Actions for AWS](https://github.com/aws-actions/)
- [DockerHub Docs](https://docs.docker.com/docker-hub/) 