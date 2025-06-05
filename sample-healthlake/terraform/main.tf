# AWS HealthLake Infrastructure - Week 1 Foundation
# GoCathLab HealthLake Engagement
# Region: us-east-1, Profile: iamadmin-datalake-healthlake-365528423741

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 0.70"
    }
  }
}

# Provider configuration
provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = "GoCathLab-HealthLake"
      Environment = var.environment
      Engagement  = "Week-1-Foundation"
      Client      = "GoCathLab"
      ManagedBy   = "Terraform"
      HIPAA       = "Eligible"
    }
  }
}

provider "awscc" {
  region  = var.aws_region
  profile = var.aws_profile
}

# Variables
variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile to use"
  type        = string
  default     = "iamadmin-datalake-healthlake-365528423741"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "gocathlab-healthlake"
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Note: Using AWS-owned encryption for Week 1 simplicity
# Customer-managed KMS keys can be added later for import/export operations

# CloudWatch Log Group for HealthLake
resource "aws_cloudwatch_log_group" "healthlake_logs" {
  name              = "/aws/healthlake/${var.project_name}"
  retention_in_days = 30
  # Using default AWS encryption for simplicity

  tags = {
    Name = "${var.project_name}-healthlake-logs"
  }
}

# IAM Role for HealthLake Data Store
resource "aws_iam_role" "healthlake_datastore_role" {
  name = "${var.project_name}-healthlake-datastore-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "healthlake.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-healthlake-datastore-role"
  }
}

# IAM Policy for HealthLake CloudWatch Logging
resource "aws_iam_policy" "healthlake_logging_policy" {
  name        = "${var.project_name}-healthlake-logging-policy"
  description = "Policy for HealthLake CloudWatch logging"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          aws_cloudwatch_log_group.healthlake_logs.arn,
          "${aws_cloudwatch_log_group.healthlake_logs.arn}:*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "healthlake_logging_attachment" {
  role       = aws_iam_role.healthlake_datastore_role.name
  policy_arn = aws_iam_policy.healthlake_logging_policy.arn
}

# S3 Bucket for data ingestion staging
resource "aws_s3_bucket" "healthlake_staging" {
  bucket = "${var.project_name}-staging-${random_string.bucket_suffix.result}"

  tags = {
    Name        = "${var.project_name}-staging"
    Purpose     = "HealthLake Data Ingestion Staging"
    HIPAAData   = "true"
  }
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "healthlake_staging_versioning" {
  bucket = aws_s3_bucket.healthlake_staging.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption (using default AWS encryption for Week 1)
resource "aws_s3_bucket_server_side_encryption_configuration" "healthlake_staging_encryption" {
  bucket = aws_s3_bucket.healthlake_staging.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "healthlake_staging_pab" {
  bucket = aws_s3_bucket.healthlake_staging.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# HealthLake Data Store
resource "awscc_healthlake_fhir_datastore" "main" {
  datastore_name         = "${var.project_name}-fhir-datastore"
  datastore_type_version = "R4"

  # Enable preload for synthetic data (Week 1 requirement)
  preload_data_config = {
    preload_data_type = "SYNTHEA"
  }

  # AWS-owned encryption (default) - no KMS configuration needed
  sse_configuration = {
    kms_encryption_config = {
      cmk_type = "AWS_OWNED_KMS_KEY"
    }
  }

  # Identity provider configuration (for future SMART on FHIR if needed)
  identity_provider_configuration = {
    authorization_strategy = "AWS_AUTH"
  }

  # Note: awscc provider doesn't support tags in the same way as aws provider
  # Tags will be applied via default_tags in the provider configuration

  depends_on = [
    aws_iam_role_policy_attachment.healthlake_logging_attachment
  ]
}

# IAM Role for data import operations
resource "aws_iam_role" "healthlake_import_role" {
  name = "${var.project_name}-healthlake-import-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "healthlake.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-healthlake-import-role"
  }
}

# IAM Policy for S3 access during import
resource "aws_iam_policy" "healthlake_import_policy" {
  name        = "${var.project_name}-healthlake-import-policy"
  description = "Policy for HealthLake to access S3 for data import"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.healthlake_staging.arn,
          "${aws_s3_bucket.healthlake_staging.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "healthlake_import_attachment" {
  role       = aws_iam_role.healthlake_import_role.name
  policy_arn = aws_iam_policy.healthlake_import_policy.arn
}

# IAM Role for client team access
resource "aws_iam_role" "gocathlab_healthlake_access" {
  name = "${var.project_name}-client-access-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "gocathlab-healthlake-access"
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-client-access-role"
  }
}

# IAM Policy for client HealthLake read access
resource "aws_iam_policy" "gocathlab_healthlake_read_policy" {
  name        = "${var.project_name}-client-read-policy"
  description = "Read access to HealthLake for GoCathLab team"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "healthlake:DescribeFHIRDatastore",
          "healthlake:DescribeFHIRImportJob",
          "healthlake:DescribeFHIRExportJob",
          "healthlake:ListFHIRDatastores",
          "healthlake:ReadResource",
          "healthlake:SearchWithGet",
          "healthlake:SearchWithPost"
        ]
        Resource = [
          awscc_healthlake_fhir_datastore.main.datastore_arn,
          "${awscc_healthlake_fhir_datastore.main.datastore_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:GetLogEvents"
        ]
        Resource = [
          aws_cloudwatch_log_group.healthlake_logs.arn,
          "${aws_cloudwatch_log_group.healthlake_logs.arn}:*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "gocathlab_healthlake_read_attachment" {
  role       = aws_iam_role.gocathlab_healthlake_access.name
  policy_arn = aws_iam_policy.gocathlab_healthlake_read_policy.arn
}

# Outputs
output "healthlake_datastore_id" {
  description = "ID of the HealthLake FHIR datastore"
  value       = awscc_healthlake_fhir_datastore.main.datastore_id
}

output "healthlake_datastore_arn" {
  description = "ARN of the HealthLake FHIR datastore"
  value       = awscc_healthlake_fhir_datastore.main.datastore_arn
}

output "healthlake_datastore_endpoint" {
  description = "Endpoint URL of the HealthLake FHIR datastore"
  value       = awscc_healthlake_fhir_datastore.main.datastore_endpoint
}

output "staging_bucket_name" {
  description = "Name of the S3 staging bucket for data ingestion"
  value       = aws_s3_bucket.healthlake_staging.bucket
}

output "staging_bucket_arn" {
  description = "ARN of the S3 staging bucket"
  value       = aws_s3_bucket.healthlake_staging.arn
}

output "kms_key_id" {
  description = "KMS encryption type (AWS-owned for Week 1)"
  value       = "AWS_OWNED_KMS_KEY"
}

output "kms_key_arn" {
  description = "KMS encryption type (AWS-owned for Week 1)" 
  value       = "AWS_OWNED_KMS_KEY"
}

output "import_role_arn" {
  description = "ARN of the IAM role for data import operations"
  value       = aws_iam_role.healthlake_import_role.arn
}

output "client_access_role_arn" {
  description = "ARN of the IAM role for client team access"
  value       = aws_iam_role.gocathlab_healthlake_access.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for HealthLake logs"
  value       = aws_cloudwatch_log_group.healthlake_logs.name
}