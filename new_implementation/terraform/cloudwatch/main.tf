variable "log_group_name" { default = "/ecs/diplomacy-app" }

resource "aws_cloudwatch_log_group" "ecs" {
  name              = var.log_group_name
  retention_in_days = 30
  tags = { Name = "diplomacy-app-log-group" }
} 