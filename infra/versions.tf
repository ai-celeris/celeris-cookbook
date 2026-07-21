terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Remote state is intentionally not configured yet. Once the hosting
  # account is chosen, mirror the celeris-apps convention, e.g.:
  #
  # backend "s3" {
  #   bucket       = "<tfstate-bucket-for-the-chosen-account>"
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

# CloudFront ACM certificates must live in us-east-1.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project = "celeris-cookbook"
    }
  }
}
