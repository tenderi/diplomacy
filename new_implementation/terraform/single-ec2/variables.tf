variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH to the instance"
  type        = string
  default     = "0.0.0.0/0" # Restrict this to your IP for security
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

variable "telegram_bot_token" {
  description = "Telegram bot token"
  type        = string
  sensitive   = true
}

variable "key_name" {
  description = "AWS EC2 Key Pair name for SSH access"
  type        = string
}

variable "use_elastic_ip" {
  description = "Whether to associate an Elastic IP (costs $3.65/month but provides static IP)"
  type        = bool
  default     = false
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
} 