terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket = "diplomacy-tfstate-tenderi"
    key    = "ec2-single-instance/terraform.tfstate"
    region = "eu-north-1"

    # Terraform 1.10+ supports native state locking via S3 — no DynamoDB needed.
    use_lockfile = true
    encrypt      = true
  }
}
