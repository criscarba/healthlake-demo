# ============================================================================
# Week 3: Medical NLP Infrastructure for GoCathLab HealthLake
# Add to existing Terraform configuration
# ============================================================================

# # Data sources
# data "aws_region" "current" {}

# Random ID for unique bucket naming (should already exist from previous weeks)
# random_string.bucket_suffix

# Additional S3 buckets for NLP processing
resource "aws_s3_bucket" "nlp_input" {
  bucket = "${var.project_name}-nlp-input-${random_string.bucket_suffix.result}"

  tags = {
    Name        = "NLP Input Bucket"
    Project     = var.project_name
    Environment = var.environment
    Week        = "3"
    Purpose     = "Medical NLP Input Data"
  }
}

resource "aws_s3_bucket" "nlp_output" {
  bucket = "${var.project_name}-nlp-output-${random_string.bucket_suffix.result}"

  tags = {
    Name        = "NLP Output Bucket"
    Project     = var.project_name
    Environment = var.environment
    Week        = "3"
    Purpose     = "Medical NLP Results"
  }
}

resource "aws_s3_bucket" "audio_input" {
  bucket = "${var.project_name}-audio-input-${random_string.bucket_suffix.result}"

  tags = {
    Name        = "Audio Input Bucket"
    Project     = var.project_name
    Environment = var.environment
    Week        = "3"
    Purpose     = "Cath Lab Audio Recordings"
  }
}

# S3 bucket versioning and encryption
resource "aws_s3_bucket_versioning" "nlp_input_versioning" {
  bucket = aws_s3_bucket.nlp_input.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "nlp_output_versioning" {
  bucket = aws_s3_bucket.nlp_output.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "audio_input_versioning" {
  bucket = aws_s3_bucket.audio_input.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "nlp_input_encryption" {
  bucket = aws_s3_bucket.nlp_input.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "nlp_output_encryption" {
  bucket = aws_s3_bucket.nlp_output.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audio_input_encryption" {
  bucket = aws_s3_bucket.audio_input.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ============================================================================
# IAM Role for Medical NLP Lambda Functions
# ============================================================================

resource "aws_iam_role" "nlp_lambda_role" {
  name = "${var.project_name}-nlp-lambda-role"

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
    Name    = "NLP Lambda Execution Role"
    Project = var.project_name
    Week    = "3"
  }
}

resource "aws_iam_policy" "nlp_lambda_policy" {
  name        = "${var.project_name}-nlp-lambda-policy"
  description = "Policy for NLP Lambda functions"

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
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.nlp_input.arn}/*",
          "${aws_s3_bucket.nlp_output.arn}/*",
          "${aws_s3_bucket.audio_input.arn}/*",
          "${aws_s3_bucket.fhir_source_data.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.nlp_input.arn,
          aws_s3_bucket.nlp_output.arn,
          aws_s3_bucket.audio_input.arn,
          aws_s3_bucket.fhir_source_data.arn
        ]
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
          "transcribe:StartMedicalTranscriptionJob",
          "transcribe:GetMedicalTranscriptionJob",
          "transcribe:ListMedicalTranscriptionJobs"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "healthlake:*"
        ]
        Resource = [
          awscc_healthlake_fhir_datastore.main.datastore_arn,
          "${awscc_healthlake_fhir_datastore.main.datastore_arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "nlp_lambda_policy_attachment" {
  role       = aws_iam_role.nlp_lambda_role.name
  policy_arn = aws_iam_policy.nlp_lambda_policy.arn
}

# ============================================================================
# Lambda Function: Clinical Notes NLP Processor
# ============================================================================

resource "aws_lambda_function" "clinical_notes_nlp" {
  filename         = "clinical_notes_nlp.zip"
  function_name    = "${var.project_name}-clinical-notes-nlp"
  role            = aws_iam_role.nlp_lambda_role.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 300

  environment {
    variables = {
      NLP_OUTPUT_BUCKET = aws_s3_bucket.nlp_output.bucket
      HEALTHLAKE_ENDPOINT = awscc_healthlake_fhir_datastore.main.datastore_endpoint
      DATASTORE_ID = awscc_healthlake_fhir_datastore.main.datastore_id
    }
  }

  tags = {
    Name    = "Clinical Notes NLP Processor"
    Project = var.project_name
    Week    = "3"
  }

  depends_on = [
    data.archive_file.lambda_zip_clinical_notes_nlp,
    aws_iam_role_policy_attachment.nlp_lambda_policy_attachment
    ]
}

data "archive_file" "lambda_zip_clinical_notes_nlp" {
  type        = "zip"
  output_path = "clinical_notes_nlp.zip"
  source {
    content  = file("${path.module}/clinical_notes_nlp.py")
    filename = "index.py"
  }
}

# ============================================================================
# Lambda Function: Audio Transcription Processor
# ============================================================================

resource "aws_lambda_function" "audio_transcription" {
  filename         = "audio_transcription.zip"
  function_name    = "${var.project_name}-audio-transcription"
  role            = aws_iam_role.nlp_lambda_role.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 300

  environment {
    variables = {
      NLP_OUTPUT_BUCKET = aws_s3_bucket.nlp_output.bucket
      TRANSCRIPTION_RESULTS_BUCKET = aws_s3_bucket.nlp_output.bucket
    }
  }

  tags = {
    Name    = "Audio Transcription Processor"
    Project = var.project_name
    Week    = "3"
  }

  depends_on = [
    data.archive_file.lambda_zip_audio_transcription,
    aws_iam_role_policy_attachment.nlp_lambda_policy_attachment
  ]
}

data "archive_file" "lambda_zip_audio_transcription" {
  type        = "zip"
  output_path = "audio_transcription.zip"
  source {
    content  = file("${path.module}/audio_transcription.py")
    filename = "index.py"
  }
}
# ============================================================================
# Lambda Function: FHIR Resource Creator
# ============================================================================

resource "aws_lambda_function" "fhir_resource_creator" {
  filename         = "fhir_resource_creator.zip"
  function_name    = "${var.project_name}-fhir-resource-creator"
  role            = aws_iam_role.nlp_lambda_role.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 300

  environment {
    variables = {
      HEALTHLAKE_ENDPOINT = awscc_healthlake_fhir_datastore.main.datastore_endpoint
      DATASTORE_ID = awscc_healthlake_fhir_datastore.main.datastore_id
      NLP_OUTPUT_BUCKET = aws_s3_bucket.nlp_output.bucket
    }
  }

  tags = {
    Name    = "FHIR Resource Creator"
    Project = var.project_name
    Week    = "3"
  }

  depends_on = [
    data.archive_file.lambda_zip_fhir_resource_creator,
    aws_iam_role_policy_attachment.nlp_lambda_policy_attachment
  ]
}

data "archive_file" "lambda_zip_fhir_resource_creator" {
  type        = "zip"
  output_path = "fhir_resource_creator.zip"
  source {
    content  = file("${path.module}/fhir_resource_creator.py")
    filename = "index.py"
  }
}

# ============================================================================
# S3 Event Notifications for NLP Processing
# ============================================================================

resource "aws_s3_bucket_notification" "nlp_input_notification" {
  bucket = aws_s3_bucket.nlp_input.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.clinical_notes_nlp.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clinical-notes/"
    filter_suffix       = ".txt"
  }

  depends_on = [aws_lambda_permission.nlp_input_s3_trigger]
}

resource "aws_s3_bucket_notification" "audio_input_notification" {
  bucket = aws_s3_bucket.audio_input.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.audio_transcription.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "audio/"
    filter_suffix       = ".wav"
  }

  depends_on = [aws_lambda_permission.audio_input_s3_trigger]
}

# Add another S3 notification for the output bucket
resource "aws_s3_bucket_notification" "nlp_output_notification" {
  bucket = aws_s3_bucket.nlp_output.id

  # Trigger on clinical notes processing
  lambda_function {
    lambda_function_arn = aws_lambda_function.fhir_resource_creator.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "processed/"
    filter_suffix       = ".json"
  }

  # Trigger on audio transcription results
  lambda_function {
    lambda_function_arn = aws_lambda_function.fhir_resource_creator.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "transcriptions/"
    filter_suffix       = "_transcription_results.json"
  }

  depends_on = [aws_lambda_permission.nlp_output_s3_trigger]
}

resource "aws_lambda_permission" "nlp_output_s3_trigger" {
  statement_id  = "AllowExecutionFromS3NLPOutput"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fhir_resource_creator.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.nlp_output.arn
}

# ============================================================================
# Lambda Permissions for S3 Triggers
# ============================================================================

resource "aws_lambda_permission" "nlp_input_s3_trigger" {
  statement_id  = "AllowExecutionFromS3NLPInput"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.clinical_notes_nlp.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.nlp_input.arn
}

resource "aws_lambda_permission" "audio_input_s3_trigger" {
  statement_id  = "AllowExecutionFromS3AudioInput"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.audio_transcription.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.audio_input.arn
}

# ============================================================================
# CloudWatch Log Groups for Lambda Functions
# ============================================================================

resource "aws_cloudwatch_log_group" "clinical_notes_nlp_logs" {
  name              = "/aws/lambda/${aws_lambda_function.clinical_notes_nlp.function_name}"
  retention_in_days = 14

  tags = {
    Name    = "Clinical Notes NLP Logs"
    Project = var.project_name
    Week    = "3"
  }
}

resource "aws_cloudwatch_log_group" "audio_transcription_logs" {
  name              = "/aws/lambda/${aws_lambda_function.audio_transcription.function_name}"
  retention_in_days = 14

  tags = {
    Name    = "Audio Transcription Logs"
    Project = var.project_name
    Week    = "3"
  }
}

resource "aws_cloudwatch_log_group" "fhir_resource_creator_logs" {
  name              = "/aws/lambda/${aws_lambda_function.fhir_resource_creator.function_name}"
  retention_in_days = 14

  tags = {
    Name    = "FHIR Resource Creator Logs"
    Project = var.project_name
    Week    = "3"
  }
}

# ============================================================================
# EventBridge Rule for NLP Processing Orchestration
# ============================================================================

# resource "aws_cloudwatch_event_rule" "nlp_processing_complete" {
#   name        = "${var.project_name}-nlp-processing-complete"
#   description = "Triggered when NLP processing is complete"

#   event_pattern = jsonencode({
#     source      = ["aws.lambda"]
#     detail-type = ["Lambda Function Invocation Result - Success"]
#     detail = {
#       functionName = [aws_lambda_function.clinical_notes_nlp.function_name]
#     }
#   })

#   tags = {
#     Name    = "NLP Processing Complete Rule"
#     Project = var.project_name
#     Week    = "3"
#   }
# }

# resource "aws_cloudwatch_event_target" "fhir_creator_target" {
#   rule      = aws_cloudwatch_event_rule.nlp_processing_complete.name
#   target_id = "FHIRResourceCreatorTarget"
#   arn       = aws_lambda_function.fhir_resource_creator.arn
# }

# resource "aws_lambda_permission" "allow_eventbridge" {
#   statement_id  = "AllowExecutionFromEventBridge"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.fhir_resource_creator.function_name
#   principal     = "events.amazonaws.com"
#   source_arn    = aws_cloudwatch_event_rule.nlp_processing_complete.arn
# }

# ============================================================================
# Output Values for Week 3
# ============================================================================

output "nlp_input_bucket" {
  description = "S3 bucket for NLP input data"
  value       = aws_s3_bucket.nlp_input.bucket
}

output "nlp_output_bucket" {
  description = "S3 bucket for NLP output results"
  value       = aws_s3_bucket.nlp_output.bucket
}

output "audio_input_bucket" {
  description = "S3 bucket for audio input files"
  value       = aws_s3_bucket.audio_input.bucket
}

output "clinical_notes_nlp_function" {
  description = "Clinical Notes NLP Lambda function name"
  value       = aws_lambda_function.clinical_notes_nlp.function_name
}

output "audio_transcription_function" {
  description = "Audio Transcription Lambda function name"
  value       = aws_lambda_function.audio_transcription.function_name
}

output "fhir_resource_creator_function" {
  description = "FHIR Resource Creator Lambda function name"
  value       = aws_lambda_function.fhir_resource_creator.function_name
}