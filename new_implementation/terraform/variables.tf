variable "aws_region" {
  description = "AWS region to deploy resources in"
  type        = string
  default     = "eu-west-1"
}

variable "db_name" {
  description = "Database name for Diplomacy app"
  type        = string
  default     = "diplomacy"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "diplomacy"
}

variable "db_password" {
  description = "Database password"
  type        = string
  default     = "diplomacy"
  sensitive   = true
}

# variable "app_image" {
#   description = "Docker image for Diplomacy app"
#   type        = string
#   default     = "DOCKERHUB_USERNAME/diplomacy:latest"
# }

variable "telegram_bot_token" {
  description = "Telegram bot token"
  type        = string
  sensitive   = true
} 