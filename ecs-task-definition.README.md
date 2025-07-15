# ECS Task Definition: diplomacy-app-task

This file (`ecs-task-definition.json`) defines how AWS ECS should run the Diplomacy app (API + Telegram bot) as a containerized service.

## Key Fields
- `family`: Name for this task definition family (e.g., `diplomacy-app-task`).
- `networkMode`: Use `awsvpc` for Fargate (recommended).
- `requiresCompatibilities`: Use `FARGATE` for serverless containers.
- `cpu`/`memory`: Adjust as needed for your workload (default: 512 CPU, 1024 MB RAM).
- `containerDefinitions`:
  - `name`: Name of the container (referenced in the pipeline and ECS service).
  - `image`: Docker image to run (e.g., `DOCKERHUB_USERNAME/diplomacy:latest`).
  - `portMappings`: Expose port 8000 for the API.
  - `environment`: Set required environment variables:
    - `SQLALCHEMY_DATABASE_URL`: Connection string for your RDS Postgres instance.
    - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token (can use ECS secrets).
    - `DIPLOMACY_API_URL`: Should be `http://localhost:8000`.
  - `logConfiguration`: Configure AWS CloudWatch logging (edit group/region as needed).

## How to Use
1. Edit this file:
   - Replace `DOCKERHUB_USERNAME` with your DockerHub username.
   - Replace `YOUR_RDS_ENDPOINT` with your RDS endpoint.
   - Replace `YOUR_TELEGRAM_BOT_TOKEN` and `YOUR_AWS_REGION` as needed.
2. Register this task definition in the ECS Console or via AWS CLI:
   ```sh
   aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
   ```
3. Reference this task definition in your ECS service and in the GitHub Actions pipeline.

## See Also
- [AWS ECS Task Definition Docs](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html)
- [Deployment Guide](new_implementation/README_DEPLOY_AWS.md) 