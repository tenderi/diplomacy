terraform {
  required_version = ">= 1.3.0"
  backend "s3" {
    bucket = "diplomacy-bot-test-polarsquad"
    key    = "diplomacy-terraform-state-single-ec2"
    region = "eu-west-1"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }
}

provider "aws" {
  region = "eu-west-1"
}

# Data source for default VPC (free)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security group for EC2 instance
resource "aws_security_group" "diplomacy" {
  name_prefix = "diplomacy-single-"
  description = "Security group for single EC2 diplomacy instance"
  vpc_id      = data.aws_vpc.default.id

  # SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # HTTP for API
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS (optional)
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Telegram bot webhook port (if needed)
  ingress {
    from_port   = 8081
    to_port     = 8081
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "diplomacy-single-sg"
  }
}

# Latest Ubuntu 22.04 LTS AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Single EC2 instance
resource "aws_instance" "diplomacy" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"

  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.diplomacy.id]
  associate_public_ip_address = true

  key_name = var.key_name

  user_data_base64 = base64encode(templatefile("${path.module}/user_data.sh", {
    db_name            = var.db_name
    db_username        = var.db_username
    db_password        = var.db_password
    telegram_bot_token = var.telegram_bot_token
    diplomacy_api_url  = "http://localhost:8000"
  }))

  root_block_device {
    volume_type = "gp3"
    volume_size = 10 # 10GB should be enough
    encrypted   = true
  }

  tags = {
    Name = "diplomacy-single-instance"
    Type = "diplomacy-server"
  }
}

# Elastic IP (optional, for static IP)
resource "aws_eip" "diplomacy" {
  count    = var.use_elastic_ip ? 1 : 0
  instance = aws_instance.diplomacy.id
  domain   = "vpc"

  tags = {
    Name = "diplomacy-eip"
  }
}

# Output the instance details
output "instance_id" {
  value = aws_instance.diplomacy.id
}

output "public_ip" {
  value = var.use_elastic_ip ? aws_eip.diplomacy[0].public_ip : aws_instance.diplomacy.public_ip
}

output "public_dns" {
  value = aws_instance.diplomacy.public_dns
}

output "key_name" {
  value = var.key_name
  description = "EC2 Key Pair name used for SSH access"
}

output "ssh_command" {
  value = "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${var.use_elastic_ip ? aws_eip.diplomacy[0].public_ip : aws_instance.diplomacy.public_ip}"
}

output "api_url" {
  value = "http://${var.use_elastic_ip ? aws_eip.diplomacy[0].public_ip : aws_instance.diplomacy.public_ip}:8000"
} 