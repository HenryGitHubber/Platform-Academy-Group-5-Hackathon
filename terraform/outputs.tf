# ── Data bucket ───────────────────────────────────────────────────────────────
output "data_bucket_name" {
  description = "Name of the S3 bucket holding raw intake data and processed output"
  value       = aws_s3_bucket.data_bucket.id
}

output "processed_data_url" {
  description = "Public URL of the processed output file — paste this into your frontend fetch() call"
  value       = "https://${aws_s3_bucket.data_bucket.bucket_regional_domain_name}/processed/all_data.json"
}

# ── Frontend bucket ───────────────────────────────────────────────────────────
output "frontend_bucket_name" {
  description = "Name of the S3 bucket hosting the static frontend"
  value       = aws_s3_bucket.frontend_bucket.id
}

output "frontend_url" {
  description = "Public URL of the static website — open this in your browser"
  value       = "http://${aws_s3_bucket.frontend_bucket.bucket}.s3-website-${var.aws_region}.amazonaws.com"
}

# ── Lambda ────────────────────────────────────────────────────────────────────
output "lambda_function_name" {
  description = "Lambda function name — use this to test manually in the AWS console"
  value       = aws_lambda_function.data_processor.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.data_processor.arn
}

# ── Cognito ───────────────────────────────────────────────────────────────────
output "cognito_user_pool_id" {
  description = "Cognito User Pool ID — needed in the frontend auth config"
  value       = aws_cognito_user_pool.academy_pool.id
}

output "cognito_client_id" {
  description = "Cognito App Client ID — needed in the frontend auth config"
  value       = aws_cognito_user_pool_client.academy_client.id
}

output "cognito_hosted_ui_url" {
  description = "Cognito hosted login page URL"
  value       = "https://${aws_cognito_user_pool_domain.academy_domain.domain}.auth.${var.aws_region}.amazoncognito.com/login?client_id=${aws_cognito_user_pool_client.academy_client.id}&response_type=token&scope=email+openid+profile&redirect_uri=http://localhost:3000"
}

output "aws_region" {
  description = "AWS region used for deployment"
  value       = var.aws_region
}
