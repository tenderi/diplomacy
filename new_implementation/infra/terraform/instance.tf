# Latest Ubuntu 24.04 LTS (Noble) AMI for the instance's architecture.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "diplomacy" {
  ami                  = data.aws_ami.ubuntu.id
  instance_type        = var.instance_type
  subnet_id            = data.aws_subnet.primary.id
  iam_instance_profile = aws_iam_instance_profile.ec2.name

  vpc_security_group_ids      = [aws_security_group.diplomacy.id]
  associate_public_ip_address = true
  key_name                    = var.key_name

  # IMDSv2 only — blocks legacy SSRF metadata attacks.
  metadata_options {
    http_tokens                 = "required"
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gb
    encrypted             = true
    delete_on_termination = true
  }

  user_data_replace_on_change = false
  user_data = templatefile("${path.module}/user_data.sh", {
    aws_region  = var.aws_region
    ssm_prefix  = local.ssm_prefix
    github_repo = "${var.github_owner}/${var.github_repo}"
  })

  tags = {
    Name = "diplomacy"
  }

  # Recreate-don't-update for changes that would force EC2 replacement.
  # The only thing we expect to mutate often is the user_data, and that's
  # explicitly set to NOT replace (above) — re-running the bootstrap on an
  # existing instance is what `terraform taint aws_instance.diplomacy`
  # is for, manually.
  lifecycle {
    ignore_changes = [ami]
  }
}
