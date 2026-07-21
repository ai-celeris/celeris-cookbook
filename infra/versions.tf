terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Remote state is intentionally not configured yet. This root targets the
  # SAME AWS account as the docs.celeris.ai distribution (diffusion-llm-service
  # infra/management); once confirmed, mirror that account's tfstate bucket:
  #
  # backend "s3" {
  #   bucket       = "<tfstate-bucket-for-the-docs-account>"
  #   key          = "celeris-cookbook/terraform.tfstate"
  #   region       = "us-west-2"
  #   encrypt      = true
  #   use_lockfile = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = "celeris-cookbook"
    }
  }
}
