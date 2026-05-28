# Use the default VPC. Free. Always exists in a fresh AWS account.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Pin to the first AZ's default subnet so the EC2 instance lands somewhere
# stable across applies.
data "aws_subnet" "primary" {
  id = sort(data.aws_subnets.default.ids)[0]
}

resource "aws_security_group" "diplomacy" {
  name_prefix = "diplomacy-"
  description = "Inbound: HTTP(80), optional SSH(22). Outbound: all."
  vpc_id      = data.aws_vpc.default.id

  # HTTP — Nginx reverse proxy. The API itself stays on 8000 bound to localhost.
  ingress {
    description = "HTTP via Nginx"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH — only if a key pair is configured AND the CIDR is set.
  # Use dynamic so the rule is omitted entirely when key_name is null.
  dynamic "ingress" {
    for_each = var.key_name == null ? [] : [1]
    content {
      description = "SSH (key-based)"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [var.allowed_ssh_cidr]
    }
  }

  egress {
    description = "All outbound (apt, pip, SSM, Telegram API)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "diplomacy-sg"
  }
}
