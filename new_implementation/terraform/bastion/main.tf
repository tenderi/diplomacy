variable "vpc_id" {}
variable "public_subnet_id" {}
variable "allowed_ssh_cidr" {}
variable "key_name" {}

resource "aws_security_group" "bastion" {
  name        = "bastion-sg"
  description = "Allow SSH access to bastion host"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_instance" "bastion" {
  ami           = data.aws_ami.amazon_linux_2.id
  instance_type = "t3.micro"
  subnet_id     = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.bastion.id]
  key_name      = var.key_name
  associate_public_ip_address = true
  tags = {
    Name = "diplomacy-bastion"
  }
}

output "bastion_public_ip" {
  value = aws_instance.bastion.public_ip
  description = "Public IP of the bastion host"
}

output "bastion_security_group_id" {
  value = aws_security_group.bastion.id
  description = "Security group ID of the bastion host"
} 