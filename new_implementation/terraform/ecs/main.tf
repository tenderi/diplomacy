variable "vpc_id" {}
variable "private_subnet_ids" { type = list(string) }
variable "ecs_sg_id" {}
variable "app_image" { description = "Docker image for Diplomacy app" }
variable "db_endpoint" { description = "RDS endpoint" }
variable "db_name" { description = "Database name" }
variable "db_username" { description = "Database username" }
variable "db_password" { description = "Database password" }
variable "telegram_bot_token" { description = "Telegram bot token" }
variable "target_group_arn" { description = "ALB target group ARN" }
variable "aws_region" { description = "AWS region for ECS logs" }

resource "aws_ecs_cluster" "main" {
  name = "diplomacy-cluster"
}

resource "aws_ecs_task_definition" "app" {
  family                   = "diplomacy-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  container_definitions    = file("${path.module}/container-definitions.json")
}

resource "aws_ecs_service" "app" {
  name            = "diplomacy-app-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  launch_type     = "FARGATE"
  desired_count   = 1
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_sg_id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "diplomacy-app"
    container_port   = 8000
  }
  depends_on = [aws_ecs_task_definition.app]
}

# Stub for Telegram bot service (future extension)
# resource "aws_ecs_task_definition" "bot" { ... }
# resource "aws_ecs_service" "bot" { ... }

resource "aws_iam_role" "ecs_task_execution" {
  name = "diplomacy-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role_policy.json
}

data "aws_iam_policy_document" "ecs_task_assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_secrets_access" {
  name = "ecs-secrets-access"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue"
        ],
        Resource = "arn:aws:secretsmanager:eu-west-1:511302509360:secret:diplomacy/telegram-bot-token*"
      }
    ]
  })
} 