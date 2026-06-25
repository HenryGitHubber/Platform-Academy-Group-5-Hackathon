terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

# ── Provider ──────────────────────────────────────────────────────────────────
provider "aws" {
  region = var.aws_region
}

# ── Current AWS account (used to create unique bucket names) ──────────────────
data "aws_caller_identity" "current" {}

# ── Reusable locals ───────────────────────────────────────────────────────────
locals {
  name_prefix = "${var.project_name}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id
}
