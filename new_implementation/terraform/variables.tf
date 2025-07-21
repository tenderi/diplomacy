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

variable "github_actions_role_arn" {
  description = "ARN of the GitHub Actions OIDC role created by the bootstrap stack"
  type        = string
  default     = "arn:aws:iam::511302509360:role/github-actions-oidc"
} 

variable "bastion_key_name" {
  description = "SSH key name for the bastion host EC2 instance"
  type        = string
} 