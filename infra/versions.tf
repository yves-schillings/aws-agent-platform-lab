terraform {
  required_version = ">= 1.12.2, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.66.0"
    }
  }
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]
  default_tags {
    tags = {
      Project   = var.name_prefix
      ManagedBy = "Terraform"
      DataClass = "synthetic-only"
      ExpiresOn = var.expires_on
    }
  }
}
