variable "aws_region" {
  description = "AWS region for all resources. Default eu-north-1 (Stockholm) — closest to Helsinki."
  type        = string
  default     = "eu-north-1"
}

variable "instance_type" {
  description = "EC2 instance type. t3.micro is free tier for 12 months. After that ~$8.50/month in eu-north-1."
  type        = string
  default     = "t3.micro"
}

variable "root_volume_size_gb" {
  description = "Size of the root EBS volume in GB. 10 GB is plenty; free tier covers 30 GB gp3."
  type        = number
  default     = 10
}

variable "key_name" {
  description = "AWS EC2 Key Pair name for SSH access. Create one in the AWS console; the public key only is stored in AWS. SSM Session Manager works without this — only set if you want SSH too."
  type        = string
  default     = null
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH on port 22. Should be your home/office IP, e.g. \"203.0.113.42/32\". Ignored unless key_name is set."
  type        = string
  default     = "0.0.0.0/0"
}

variable "github_owner" {
  description = "GitHub user/org that owns the repo. Used to scope the OIDC trust policy."
  type        = string
  default     = "tenderi"
}

variable "github_repo" {
  description = "GitHub repo name. Combined with github_owner to scope OIDC trust to a specific repo."
  type        = string
  default     = "diplomacy"
}

variable "github_deploy_branches" {
  description = "List of branches whose pushes can assume the deploy role. Keep this small."
  type        = list(string)
  default     = ["main"]
}

variable "budget_monthly_usd" {
  description = "Monthly AWS budget alert threshold in USD. Email is sent at 80%% and 100%% of this."
  type        = number
  default     = 5
}

variable "budget_alert_email" {
  description = "Email to receive budget alerts. Leave empty to skip budget creation."
  type        = string
  default     = ""
}
