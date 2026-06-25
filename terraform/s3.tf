# ═══════════════════════════════════════════════════════════════════════════════
#  S3 — DATA BUCKET
#  Holds raw intake JSON files (raw/) and Lambda-processed output (processed/).
#  The frontend fetches processed/all_data.json directly from this bucket.
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_s3_bucket" "data_bucket" {
  bucket        = "${local.name_prefix}-data-${local.account_id}"
  force_destroy = true # allows terraform destroy to empty the bucket

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Purpose     = "Raw intake data and processed output"
  }
}

# Allow public access so the frontend can fetch processed/all_data.json
resource "aws_s3_bucket_public_access_block" "data_bucket" {
  bucket = aws_s3_bucket.data_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# Bucket policy: public read ONLY on the processed/ prefix
resource "aws_s3_bucket_policy" "data_bucket_policy" {
  bucket = aws_s3_bucket.data_bucket.id

  # Must wait for the public access block to be removed first
  depends_on = [aws_s3_bucket_public_access_block.data_bucket]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadProcessed"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.data_bucket.arn}/processed/*"
      }
    ]
  })
}

# CORS: allow the frontend (hosted on the frontend bucket) to fetch processed data
resource "aws_s3_bucket_cors_configuration" "data_bucket_cors" {
  bucket = aws_s3_bucket.data_bucket.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["*"] # tighten to frontend URL after deployment if needed
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# S3 event notification: trigger the Lambda whenever a file lands in raw/
resource "aws_s3_bucket_notification" "data_bucket_notification" {
  bucket = aws_s3_bucket.data_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.data_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "raw/"
    filter_suffix       = ".json"
  }

  # Must wait for the Lambda permission granting S3 invoke rights
  depends_on = [aws_lambda_permission.allow_s3_invoke]
}

# ── Upload raw data files to S3 on every terraform apply ─────────────────────
# When the 2026 files are ready, add them here (or upload manually to raw/).

resource "aws_s3_object" "employee_data" {
  bucket = aws_s3_bucket.data_bucket.id
  key    = "raw/employee_data.json"
  source = "${path.module}/../front_end/employee_data/employee_data.json"
  etag   = filemd5("${path.module}/../front_end/employee_data/employee_data.json")
}

resource "aws_s3_object" "cost_data" {
  bucket = aws_s3_bucket.data_bucket.id
  key    = "raw/cost_data.json"
  source = "${path.module}/../front_end/cost_data/cost_data.json"
  etag   = filemd5("${path.module}/../front_end/cost_data/cost_data.json")
}

resource "aws_s3_object" "cost_key_data" {
  bucket = aws_s3_bucket.data_bucket.id
  key    = "raw/cost_key_data.json"
  source = "${path.module}/../front_end/cost_data/cost_key_data.json"
  etag   = filemd5("${path.module}/../front_end/cost_data/cost_key_data.json")
}

resource "aws_s3_object" "questionnaire" {
  bucket = aws_s3_bucket.data_bucket.id
  key    = "raw/questionnaire.json"
  source = "${path.module}/../front_end/questionnaire_data/questionnaire.json"
  etag   = filemd5("${path.module}/../front_end/questionnaire_data/questionnaire.json")
}

resource "aws_s3_object" "questionnaire_answers" {
  bucket = aws_s3_bucket.data_bucket.id
  key    = "raw/questionnaire_answers.json"
  source = "${path.module}/../front_end/questionnaire_data/questionnaire_answers.json"
  etag   = filemd5("${path.module}/../front_end/questionnaire_data/questionnaire_answers.json")
}


# ═══════════════════════════════════════════════════════════════════════════════
#  S3 — FRONTEND BUCKET
#  Hosts the static HTML/JS/CSS dashboard as a public website.
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_s3_bucket" "frontend_bucket" {
  bucket        = "${local.name_prefix}-frontend-${local.account_id}"
  force_destroy = true

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Purpose     = "Static frontend dashboard"
  }
}

# Enable static website hosting
resource "aws_s3_bucket_website_configuration" "frontend_website" {
  bucket = aws_s3_bucket.frontend_bucket.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html" # SPA fallback
  }
}

# Allow public access for static website
resource "aws_s3_bucket_public_access_block" "frontend_bucket" {
  bucket = aws_s3_bucket.frontend_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# Bucket policy: public read on all objects (it's a public website)
resource "aws_s3_bucket_policy" "frontend_bucket_policy" {
  bucket = aws_s3_bucket.frontend_bucket.id

  depends_on = [aws_s3_bucket_public_access_block.frontend_bucket]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadFrontend"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend_bucket.arn}/*"
      }
    ]
  })
}
