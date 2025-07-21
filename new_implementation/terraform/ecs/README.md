# ECS Module

This module provisions the ECS cluster and Fargate services for the Diplomacy server and Telegram bot.

## Task Definition Management

- The ECS task definition's container definitions are now loaded from `container-definitions.json` in this directory.
- To update the task definition, extract the `containerDefinitions` array from `ecs-task-definition.json` and save it as `container-definitions.json`.
- Only the container definitions are managed this way; other task definition parameters (family, network mode, etc.) are set in Terraform.
- This keeps Terraform as the source of truth for infrastructure, while allowing you to edit the container definition in a familiar JSON format. 