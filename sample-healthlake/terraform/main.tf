# AWS HealthLake Infrastructure - Week 3 Medical NLP Integration
# GoCathLab HealthLake Engagement - Extended for medical NLP capabilities
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
          "s3:*"
        ]
        Resource = [
          aws_s3_bucket.healthlake_staging.arn,
          "${aws_s3_bucket.healthlake_staging.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:*"
        ]
        Resource = "*"
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

# =============================================================================
# WEEK 2 ADDITIONS: DATA INGESTION PIPELINE
# =============================================================================

# S3 Bucket for Source FHIR Data
resource "aws_s3_bucket" "fhir_source_data" {
  bucket = "${var.project_name}-fhir-source-${random_string.bucket_suffix.result}"

  tags = {
    Name        = "${var.project_name}-fhir-source"
    Purpose     = "FHIR Source Data Storage"
    HIPAAData   = "true"
    DataType    = "Cardiovascular-FHIR"
  }
}

# S3 Bucket Versioning for source data
resource "aws_s3_bucket_versioning" "fhir_source_versioning" {
  bucket = aws_s3_bucket.fhir_source_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption for source data
resource "aws_s3_bucket_server_side_encryption_configuration" "fhir_source_encryption" {
  bucket = aws_s3_bucket.fhir_source_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# S3 Bucket Public Access Block for source data
resource "aws_s3_bucket_public_access_block" "fhir_source_pab" {
  bucket = aws_s3_bucket.fhir_source_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lambda execution role for data import
resource "aws_iam_role" "lambda_import_role" {
  name = "${var.project_name}-lambda-import-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-lambda-import-role"
  }
}

# IAM policy for Lambda to access HealthLake and S3
resource "aws_iam_policy" "lambda_import_policy" {
  name        = "${var.project_name}-lambda-import-policy"
  description = "Policy for Lambda to orchestrate HealthLake data imports"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "healthlake:StartFHIRImportJob",
          "healthlake:DescribeFHIRImportJob",
          "healthlake:ListFHIRImportJobs",
          "healthlake:DescribeFHIRDatastore"
        ]
        Resource = [
          awscc_healthlake_fhir_datastore.main.datastore_arn,
          "${awscc_healthlake_fhir_datastore.main.datastore_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:*"
        ]
        Resource = [
          aws_s3_bucket.fhir_source_data.arn,
          "${aws_s3_bucket.fhir_source_data.arn}/*",
          aws_s3_bucket.healthlake_staging.arn,
          "${aws_s3_bucket.healthlake_staging.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = aws_iam_role.healthlake_import_role.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_import_attachment" {
  role       = aws_iam_role.lambda_import_role.name
  policy_arn = aws_iam_policy.lambda_import_policy.arn
  
  # Force dependency on policy creation
  depends_on = [aws_iam_policy.lambda_import_policy]
}

# Lambda function for data import orchestration
resource "aws_lambda_function" "healthlake_import_orchestrator" {
  filename         = "healthlake_import.zip"
  function_name    = "${var.project_name}-import-orchestrator"
  role            = aws_iam_role.lambda_import_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300

  environment {
    variables = {
      HEALTHLAKE_DATASTORE_ID = awscc_healthlake_fhir_datastore.main.datastore_id
      HEALTHLAKE_IMPORT_ROLE_ARN = aws_iam_role.healthlake_import_role.arn
      SOURCE_BUCKET = aws_s3_bucket.fhir_source_data.bucket
      STAGING_BUCKET = aws_s3_bucket.healthlake_staging.bucket
    }
  }

  depends_on = [
    data.archive_file.lambda_zip,
    aws_iam_role_policy_attachment.lambda_import_attachment
  ]

  tags = {
    Name = "${var.project_name}-import-orchestrator"
    LastUpdated = timestamp()
  }
}

# Create Lambda deployment package
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "healthlake_import.zip"
  source {
    content  = file("${path.module}/lambda_import.py")
    filename = "lambda_function.py"
  }
}

# S3 notification to trigger Lambda when FHIR data is uploaded
resource "aws_s3_bucket_notification" "fhir_data_upload" {
  bucket = aws_s3_bucket.fhir_source_data.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.healthlake_import_orchestrator.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke]
}

# Permission for S3 to invoke Lambda
resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.healthlake_import_orchestrator.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.fhir_source_data.arn
}

# S3 objects for sample cardiovascular FHIR data
resource "aws_s3_object" "sample_patient" {
  bucket = aws_s3_bucket.fhir_source_data.bucket
  key    = "patients/cardiovascular-patient-001.json"
  content = jsonencode({
    resourceType = "Patient"
    id = "cardiovascular-patient-001"
    meta = {
      profile = ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]
    }
    identifier = [
      {
        use = "usual"
        type = {
          coding = [
            {
              system = "http://terminology.hl7.org/CodeSystem/v2-0203"
              code = "MR"
              display = "Medical Record Number"
            }
          ]
        }
        system = "http://gocathlab.com/patient-id"
        value = "CV-001"
      }
    ]
    active = true
    name = [
      {
        use = "official"
        family = "Johnson"
        given = ["Robert", "Michael"]
      }
    ]
    telecom = [
      {
        system = "phone"
        value = "(555) 123-4567"
        use = "home"
      }
    ]
    gender = "male"
    birthDate = "1965-03-15"
    address = [
      {
        use = "home"
        type = "both"
        line = ["123 Heart Lane"]
        city = "Bellingham"
        state = "WA"
        postalCode = "98225"
        country = "US"
      }
    ]
    maritalStatus = {
      coding = [
        {
          system = "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus"
          code = "M"
          display = "Married"
        }
      ]
    }
  })
  content_type = "application/json"

  tags = {
    DataType = "FHIR-Patient"
    Category = "Cardiovascular"
  }
}

resource "aws_s3_object" "sample_observation_cholesterol" {
  bucket = aws_s3_bucket.fhir_source_data.bucket
  key    = "observations/cholesterol-cv001-20241201.json"
  content = jsonencode({
    resourceType = "Observation"
    id = "cholesterol-cv001-20241201"
    meta = {
      profile = ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"]
    }
    status = "final"
    category = [
      {
        coding = [
          {
            system = "http://terminology.hl7.org/CodeSystem/observation-category"
            code = "laboratory"
            display = "Laboratory"
          }
        ]
      }
    ]
    code = {
      coding = [
        {
          system = "http://loinc.org"
          code = "2093-3"
          display = "Cholesterol [Mass/Volume] in Serum or Plasma"
        }
      ]
    }
    subject = {
      reference = "Patient/cardiovascular-patient-001"
      display = "Robert Johnson"
    }
    effectiveDateTime = "2024-12-01T09:30:00Z"
    valueQuantity = {
      value = 245
      unit = "mg/dL"
      system = "http://unitsofmeasure.org"
      code = "mg/dL"
    }
    interpretation = [
      {
        coding = [
          {
            system = "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"
            code = "H"
            display = "High"
          }
        ]
      }
    ]
    referenceRange = [
      {
        low = {
          value = 0
          unit = "mg/dL"
          system = "http://unitsofmeasure.org"
          code = "mg/dL"
        }
        high = {
          value = 200
          unit = "mg/dL"
          system = "http://unitsofmeasure.org"
          code = "mg/dL"
        }
        text = "Desirable: <200 mg/dL"
      }
    ]
  })
  content_type = "application/json"

  tags = {
    DataType = "FHIR-Observation"
    Category = "Laboratory"
    TestType = "Cholesterol"
  }
}

resource "aws_s3_object" "sample_observation_bp" {
  bucket = aws_s3_bucket.fhir_source_data.bucket
  key    = "observations/blood-pressure-cv001-20241201.json"
  content = jsonencode({
    resourceType = "Observation"
    id = "blood-pressure-cv001-20241201"
    meta = {
      profile = ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-blood-pressure"]
    }
    status = "final"
    category = [
      {
        coding = [
          {
            system = "http://terminology.hl7.org/CodeSystem/observation-category"
            code = "vital-signs"
            display = "Vital Signs"
          }
        ]
      }
    ]
    code = {
      coding = [
        {
          system = "http://loinc.org"
          code = "85354-9"
          display = "Blood pressure panel with all children optional"
        }
      ]
    }
    subject = {
      reference = "Patient/cardiovascular-patient-001"
      display = "Robert Johnson"
    }
    effectiveDateTime = "2024-12-01T09:30:00Z"
    component = [
      {
        code = {
          coding = [
            {
              system = "http://loinc.org"
              code = "8480-6"
              display = "Systolic blood pressure"
            }
          ]
        }
        valueQuantity = {
          value = 150
          unit = "mmHg"
          system = "http://unitsofmeasure.org"
          code = "mm[Hg]"
        }
      },
      {
        code = {
          coding = [
            {
              system = "http://loinc.org"
              code = "8462-4"
              display = "Diastolic blood pressure"
            }
          ]
        }
        valueQuantity = {
          value = 95
          unit = "mmHg"
          system = "http://unitsofmeasure.org"
          code = "mm[Hg]"
        }
      }
    ]
    interpretation = [
      {
        coding = [
          {
            system = "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"
            code = "H"
            display = "High"
          }
        ]
      }
    ]
  })
  content_type = "application/json"

  tags = {
    DataType = "FHIR-Observation"
    Category = "VitalSigns"
    TestType = "BloodPressure"
  }
}

resource "aws_s3_object" "sample_procedure" {
  bucket = aws_s3_bucket.fhir_source_data.bucket
  key    = "procedures/cardiac-cath-cv001-20241205.json"
  content = jsonencode({
    resourceType = "Procedure"
    id = "cardiac-cath-cv001-20241205"
    meta = {
      profile = ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-procedure"]
    }
    status = "completed"
    category = {
      coding = [
        {
          system = "http://snomed.info/sct"
          code = "387713003"
          display = "Surgical procedure"
        }
      ]
    }
    code = {
      coding = [
        {
          system = "http://www.ama-assn.org/go/cpt"
          code = "93458"
          display = "Catheter placement in coronary artery(s) for coronary angiography, including intraprocedural injection(s) for coronary angiography, imaging supervision and interpretation; with left heart catheterization including intraprocedural injection(s) for left ventriculography, when performed"
        },
        {
          system = "http://snomed.info/sct"
          code = "41976001"
          display = "Cardiac catheterization"
        }
      ]
    }
    subject = {
      reference = "Patient/cardiovascular-patient-001"
      display = "Robert Johnson"
    }
    performedDateTime = "2024-12-05T14:30:00Z"
    performer = [
      {
        actor = {
          display = "Dr. Sarah Cardiovascular, MD"
        }
        role = {
          coding = [
            {
              system = "http://snomed.info/sct"
              code = "17561000"
              display = "Cardiologist"
            }
          ]
        }
      }
    ]
    location = {
      display = "GoCathLab Cardiac Catheterization Laboratory"
    }
    reasonCode = [
      {
        coding = [
          {
            system = "http://snomed.info/sct"
            code = "194828000"
            display = "Angina"
          }
        ]
      }
    ]
    outcome = {
      coding = [
        {
          system = "http://snomed.info/sct"
          code = "385669000"
          display = "Successful"
        }
      ]
    }
    note = [
      {
        text = "Successful left heart catheterization with coronary angiography. Moderate stenosis found in LAD. Patient tolerated procedure well."
      }
    ]
  })
  content_type = "application/json"

  tags = {
    DataType = "FHIR-Procedure"
    Category = "Cardiovascular"
    ProcedureType = "Catheterization"
  }
}

# =============================================================================
# WEEK 3 ADDITIONS: MEDICAL NLP CAPABILITIES
# =============================================================================

# S3 Bucket for unstructured medical data (clinical notes, audio)
resource "aws_s3_bucket" "medical_nlp_data" {
  bucket = "${var.project_name}-medical-nlp-${random_string.bucket_suffix.result}"

  tags = {
    Name        = "${var.project_name}-medical-nlp"
    Purpose     = "Medical NLP Processing - Clinical Notes and Audio"
    HIPAAData   = "true"
    DataType    = "Unstructured-Medical"
  }
}

# S3 Bucket Versioning for medical NLP data
resource "aws_s3_bucket_versioning" "medical_nlp_versioning" {
  bucket = aws_s3_bucket.medical_nlp_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption for medical NLP data
resource "aws_s3_bucket_server_side_encryption_configuration" "medical_nlp_encryption" {
  bucket = aws_s3_bucket.medical_nlp_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# S3 Bucket Public Access Block for medical NLP data
resource "aws_s3_bucket_public_access_block" "medical_nlp_pab" {
  bucket = aws_s3_bucket.medical_nlp_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket for processed NLP results
resource "aws_s3_bucket" "nlp_results" {
  bucket = "${var.project_name}-nlp-results-${random_string.bucket_suffix.result}"

  tags = {
    Name        = "${var.project_name}-nlp-results"
    Purpose     = "Processed Medical NLP Results"
    HIPAAData   = "true"
    DataType    = "Structured-Medical-Entities"
  }
}

# S3 Bucket Encryption for NLP results
resource "aws_s3_bucket_server_side_encryption_configuration" "nlp_results_encryption" {
  bucket = aws_s3_bucket.nlp_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# S3 Bucket Public Access Block for NLP results
resource "aws_s3_bucket_public_access_block" "nlp_results_pab" {
  bucket = aws_s3_bucket.nlp_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# IAM Role for Comprehend Medical processing
resource "aws_iam_role" "comprehend_medical_role" {
  name = "${var.project_name}-comprehend-medical-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-comprehend-medical-role"
  }
}

# IAM Policy for Comprehend Medical access
resource "aws_iam_policy" "comprehend_medical_policy" {
  name        = "${var.project_name}-comprehend-medical-policy"
  description = "Policy for Lambda to access Comprehend Medical and S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "comprehendmedical:DetectEntitiesV2",
          "comprehendmedical:DetectPHI",
          "comprehendmedical:InferICD10CM",
          "comprehendmedical:InferRxNorm",
          "comprehendmedical:InferSNOMEDCT"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:*"
        ]
        Resource = [
          aws_s3_bucket.medical_nlp_data.arn,
          "${aws_s3_bucket.medical_nlp_data.arn}/*",
          aws_s3_bucket.nlp_results.arn,
          "${aws_s3_bucket.nlp_results.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "comprehend_medical_attachment" {
  role       = aws_iam_role.comprehend_medical_role.name
  policy_arn = aws_iam_policy.comprehend_medical_policy.arn
}

# IAM Role for Transcribe Medical processing
resource "aws_iam_role" "transcribe_medical_role" {
  name = "${var.project_name}-transcribe-medical-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-transcribe-medical-role"
  }
}

# IAM Policy for Transcribe Medical access
resource "aws_iam_policy" "transcribe_medical_policy" {
  name        = "${var.project_name}-transcribe-medical-policy"
  description = "Policy for Lambda to access Transcribe Medical and S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "transcribe:StartMedicalTranscriptionJob",
          "transcribe:GetMedicalTranscriptionJob",
          "transcribe:ListMedicalTranscriptionJobs"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:*"
        ]
        Resource = [
          aws_s3_bucket.medical_nlp_data.arn,
          "${aws_s3_bucket.medical_nlp_data.arn}/*",
          aws_s3_bucket.nlp_results.arn,
          "${aws_s3_bucket.nlp_results.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "transcribe_medical_attachment" {
  role       = aws_iam_role.transcribe_medical_role.name
  policy_arn = aws_iam_policy.transcribe_medical_policy.arn
}

# Lambda function for Comprehend Medical processing
resource "aws_lambda_function" "comprehend_medical_processor" {
  filename         = "comprehend_medical.zip"
  function_name    = "${var.project_name}-comprehend-medical"
  role            = aws_iam_role.comprehend_medical_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.9"
  timeout         = 900  # 15 minutes for large text processing

  environment {
    variables = {
      NLP_RESULTS_BUCKET = aws_s3_bucket.nlp_results.bucket
      HEALTHLAKE_DATASTORE_ID = awscc_healthlake_fhir_datastore.main.datastore_id
    }
  }

  depends_on = [data.archive_file.comprehend_medical_zip]

  tags = {
    Name = "${var.project_name}-comprehend-medical"
    Purpose = "Medical NLP Entity Extraction"
  }
}

# Lambda function for Transcribe Medical processing
resource "aws_lambda_function" "transcribe_medical_processor" {
  filename         = "transcribe_medical.zip"
  function_name    = "${var.project_name}-transcribe-medical"
  role            = aws_iam_role.transcribe_medical_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.9"
  timeout         = 900  # 15 minutes for audio processing

  environment {
    variables = {
      NLP_RESULTS_BUCKET = aws_s3_bucket.nlp_results.bucket
      MEDICAL_NLP_BUCKET = aws_s3_bucket.medical_nlp_data.bucket
    }
  }

  depends_on = [data.archive_file.transcribe_medical_zip]

  tags = {
    Name = "${var.project_name}-transcribe-medical"
    Purpose = "Medical Audio Transcription"
  }
}

# Create Lambda deployment packages
data "archive_file" "comprehend_medical_zip" {
  type        = "zip"
  output_path = "comprehend_medical.zip"
  source {
    content  = file("${path.module}/comprehend_medical.py")
    filename = "lambda_function.py"
  }
}

data "archive_file" "transcribe_medical_zip" {
  type        = "zip"
  output_path = "transcribe_medical.zip"
  source {
    content  = file("${path.module}/transcribe_medical.py")
    filename = "lambda_function.py"
  }
}

# S3 notification to trigger Comprehend Medical Lambda for clinical notes
resource "aws_s3_bucket_notification" "clinical_notes_upload" {
  bucket = aws_s3_bucket.medical_nlp_data.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.comprehend_medical_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clinical-notes/"
    filter_suffix       = ".txt"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke_comprehend]
}

# S3 notification to trigger Transcribe Medical Lambda for audio files
resource "aws_s3_bucket_notification" "audio_upload" {
  bucket = aws_s3_bucket.medical_nlp_data.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.transcribe_medical_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "audio/"
    filter_suffix       = ".wav"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke_transcribe]
}

# Permission for S3 to invoke Comprehend Medical Lambda
resource "aws_lambda_permission" "allow_s3_invoke_comprehend" {
  statement_id  = "AllowExecutionFromS3BucketComprehend"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.comprehend_medical_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.medical_nlp_data.arn
}

# Permission for S3 to invoke Transcribe Medical Lambda
resource "aws_lambda_permission" "allow_s3_invoke_transcribe" {
  statement_id  = "AllowExecutionFromS3BucketTranscribe"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.transcribe_medical_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.medical_nlp_data.arn
}

# Sample clinical notes for cardiovascular procedures
resource "aws_s3_object" "sample_clinical_note_angioplasty" {
  bucket = aws_s3_bucket.medical_nlp_data.bucket
  key    = "clinical-notes/angioplasty-procedure-cv001.txt"
  content = <<-EOT
PROCEDURE NOTE - PERCUTANEOUS CORONARY INTERVENTION

Patient: Robert Johnson (MRN: CV-001)
Date: December 5, 2024
Procedure: Percutaneous coronary angioplasty with drug-eluting stent placement

INDICATION:
Patient presented with unstable angina and positive stress test. Cardiac catheterization revealed 85% stenosis in the proximal left anterior descending artery.

PROCEDURE:
After informed consent, the patient was brought to the cardiac catheterization laboratory. Local anesthesia with lidocaine was administered to the right femoral artery. A 6-French arterial sheath was placed. 

Coronary angiography confirmed tight stenosis in the proximal LAD. Pre-dilatation was performed with a 2.5mm balloon. A 3.0 x 18mm drug-eluting stent (Xience Alpine) was deployed at 14 atmospheres with excellent result.

Final angiography showed 0% residual stenosis with TIMI 3 flow.

MEDICATIONS ADMINISTERED:
- Aspirin 325mg
- Clopidogrel 600mg loading dose
- Atorvastatin 80mg
- Metoprolol 25mg BID
- Unfractionated heparin per protocol

COMPLICATIONS: None

ASSESSMENT:
Successful percutaneous coronary intervention to proximal LAD with drug-eluting stent. Patient tolerated procedure well.

PLAN:
1. Continue dual antiplatelet therapy (aspirin + clopidogrel) for 12 months
2. High-intensity statin therapy
3. Beta-blocker as tolerated
4. Cardiac rehabilitation referral
5. Follow-up in 4-6 weeks

Dr. Sarah Cardiovascular, MD
Interventional Cardiology
EOT
  content_type = "text/plain"

  tags = {
    DataType = "Clinical-Note"
    Category = "Cardiovascular"
    Procedure = "Angioplasty"
  }
}

resource "aws_s3_object" "sample_clinical_note_cabg" {
  bucket = aws_s3_bucket.medical_nlp_data.bucket
  key    = "clinical-notes/cabg-consultation-cv002.txt"
  content = <<-EOT
CARDIOTHORACIC SURGERY CONSULTATION

Patient: Maria Rodriguez (MRN: CV-002)
Date: December 10, 2024

CHIEF COMPLAINT:
Chest pain and shortness of breath

HISTORY OF PRESENT ILLNESS:
65-year-old female with diabetes mellitus type 2, hypertension, and hyperlipidemia presents with 3-month history of progressively worsening chest pain and dyspnea on exertion. Cardiac catheterization revealed three-vessel coronary artery disease.

CORONARY ANATOMY:
- Left main: 50% stenosis
- LAD: 90% stenosis (proximal and mid-vessel)
- Circumflex: 80% stenosis 
- RCA: Complete occlusion (chronic total occlusion)

ECHOCARDIOGRAM:
Left ventricular ejection fraction 35%. Regional wall motion abnormalities in anterior and inferior walls.

RISK FACTORS:
- Diabetes mellitus type 2 (HbA1c 8.2%)
- Hypertension
- Hyperlipidemia (LDL 156 mg/dL)
- Former smoker (quit 2 years ago, 40 pack-year history)
- Family history of CAD

CURRENT MEDICATIONS:
- Metformin 1000mg BID
- Lisinopril 10mg daily
- Atorvastatin 40mg daily
- Aspirin 81mg daily
- Insulin glargine 20 units daily

RECOMMENDATION:
Given extensive three-vessel disease with depressed LV function, recommend coronary artery bypass grafting (CABG). Discussed risks including stroke, bleeding, infection, and need for possible reoperation.

SURGICAL PLAN:
- LIMA to LAD
- SVG to OM
- SVG to PDA

Pre-operative optimization:
- Optimize diabetes control
- Continue aspirin
- Hold metformin 48 hours pre-op
- Pulmonary function tests
- Carotid ultrasound

Dr. Michael Surgeon, MD
Cardiothoracic Surgery
EOT
  content_type = "text/plain"

  tags = {
    DataType = "Clinical-Note"
    Category = "Cardiovascular"
    Procedure = "CABG-Consultation"
  }
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

output "fhir_source_bucket_name" {
  description = "Name of the S3 bucket for FHIR source data"
  value       = aws_s3_bucket.fhir_source_data.bucket
}

output "fhir_source_bucket_arn" {
  description = "ARN of the S3 bucket for FHIR source data"
  value       = aws_s3_bucket.fhir_source_data.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function for import orchestration"
  value       = aws_lambda_function.healthlake_import_orchestrator.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function for import orchestration"
  value       = aws_lambda_function.healthlake_import_orchestrator.arn
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

# Week 3 NLP Outputs
output "medical_nlp_bucket_name" {
  description = "Name of the S3 bucket for medical NLP data"
  value       = aws_s3_bucket.medical_nlp_data.bucket
}

output "nlp_results_bucket_name" {
  description = "Name of the S3 bucket for NLP processing results"
  value       = aws_s3_bucket.nlp_results.bucket
}

output "comprehend_medical_function_name" {
  description = "Name of the Comprehend Medical Lambda function"
  value       = aws_lambda_function.comprehend_medical_processor.function_name
}

output "transcribe_medical_function_name" {
  description = "Name of the Transcribe Medical Lambda function"
  value       = aws_lambda_function.transcribe_medical_processor.function_name
}