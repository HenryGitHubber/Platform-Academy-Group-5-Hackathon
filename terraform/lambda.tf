# ═══════════════════════════════════════════════════════════════════════════════
#  LAMBDA — DATA PROCESSOR
#  Triggered by S3 uploads to raw/. Reads all intake JSON files, calculates
#  training costs, joins datasets, and writes processed/all_data.json.
# ═══════════════════════════════════════════════════════════════════════════════

# Zip the Lambda source code from the local lambda/ directory
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambda/lambda_function.py"
  output_path = "${path.module}/../lambda/lambda_function.zip"
}

# ── IAM Role ──────────────────────────────────────────────────────────────────
# The Lambda assumes this role at runtime

resource "aws_iam_role" "lambda_role" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ── IAM Policy ────────────────────────────────────────────────────────────────
# Grants the Lambda read access to raw/ and write access to processed/

resource "aws_iam_role_policy" "lambda_s3_policy" {
  name = "${local.name_prefix}-lambda-s3-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadRawData"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data_bucket.arn,
          "${aws_s3_bucket.data_bucket.arn}/raw/*"
        ]
      },
      {
        Sid    = "WriteProcessedData"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.data_bucket.arn}/processed/*"
      }
    ]
  })
}

# Attach AWS managed policy for CloudWatch Logs (Lambda execution logs)
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ── Lambda Function ───────────────────────────────────────────────────────────

resource "aws_lambda_function" "data_processor" {
  function_name    = "${local.name_prefix}-processor"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.12"
  handler          = "lambda_function.lambda_handler"
  role             = aws_iam_role.lambda_role.arn
  timeout          = 60  # seconds — enough for 376+ employee records
  memory_size      = 256 # MB

  # Pass the data bucket name as an env variable (fallback if event has no bucket)
  environment {
    variables = {
      DATA_BUCKET = aws_s3_bucket.data_bucket.id
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ── Lambda Permission ─────────────────────────────────────────────────────────
# Allows the S3 bucket to invoke the Lambda function

resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.data_bucket.arn
}
