provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "diplomacy"
      ManagedBy = "terraform"
      Repo      = "tenderi/diplomacy"
    }
  }
}
