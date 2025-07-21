# ECS Task Definition: diplomacy-app-task

This file (`ecs-task-definition.json`) defines how AWS ECS should run the Diplomacy app (API + Telegram bot) as a containerized service.

## Key Fields
- `family`: Name for this task definition family (e.g., `diplomacy-app-task`).
- `networkMode`: Use `awsvpc` for Fargate (recommended).
- `requiresCompatibilities`: Use `FARGATE` for serverless containers.
- `cpu`/`memory`: Adjust as needed for your workload (default: 512 CPU, 1024 MB RAM).
- `containerDefinitions`:
  - `name`: Name of the container (referenced in the pipeline and ECS service).
  - `image`: Docker image to run (e.g., `511302509360.dkr.ecr.eu-west-1.amazonaws.com/diplomacy-app:latest`).
  - `portMappings`: Expose port 8000 for the API.
  - `environment`: Set required environment variables:
    - `SQLALCHEMY_DATABASE_URL`: Connection string for your RDS Postgres instance (replace `<YOUR_RDS_ENDPOINT>` with your actual endpoint).
    - `DIPLOMACY_API_URL`: Should be `http://localhost:8000`.
  - `secrets`: Use AWS Secrets Manager to inject sensitive values:
    - `TELEGRAM_BOT_TOKEN`: Reference the ARN of your secret (see below).
  - `logConfiguration`: Configure AWS CloudWatch logging (group: `/ecs/diplomacy-app`, region: `eu-west-1`).

## How to Use
1. Store your Telegram bot token in AWS Secrets Manager (e.g., as `diplomacy/telegram-bot-token`).
2. In `ecs-task-definition.json`, reference the secret in the `secrets` array:
   ```json
   "secrets": [
     {
       "name": "TELEGRAM_BOT_TOKEN",
       "valueFrom": "arn:aws:secretsmanager:eu-west-1:511302509360:secret:diplomacy/telegram-bot-token"
     }
   ]
   ```
3. Remove `TELEGRAM_BOT_TOKEN` from the `environment` array if present.
4. Register this task definition in the ECS Console or via AWS CLI:
   ```sh
   aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
   ```
5. Reference this task definition in your ECS service and in the GitHub Actions pipeline.

## See Also
- [AWS ECS Task Definition Docs](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html)
- [Deployment Guide](new_implementation/README_DEPLOY_AWS.md) 