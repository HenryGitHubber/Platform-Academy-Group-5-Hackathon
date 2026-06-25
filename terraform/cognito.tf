# ═══════════════════════════════════════════════════════════════════════════════
#  COGNITO — USER AUTHENTICATION
#  Protects the dashboard with a login wall.
#  The frontend uses the hosted UI or the Cognito JS SDK to authenticate users.
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cognito_user_pool" "academy_pool" {
  name = "${local.name_prefix}-user-pool"

  # Allow sign-in with email address
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Password policy
  password_policy {
    minimum_length                   = 8
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  # Email verification message sent when a new user is created
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Platform Academy — Verify your email"
    email_message        = "Your verification code is {####}"
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# ── App Client ────────────────────────────────────────────────────────────────
# The frontend uses this client ID to interact with Cognito (no client secret
# because it's a public JavaScript app running in the browser).

resource "aws_cognito_user_pool_client" "academy_client" {
  name         = "${local.name_prefix}-app-client"
  user_pool_id = aws_cognito_user_pool.academy_pool.id

  # No client secret — public client (browser-based app)
  generate_secret = false

  # Token validity
  access_token_validity  = 1   # hours
  id_token_validity      = 1   # hours
  refresh_token_validity = 30  # days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Allowed OAuth flows (needed if using Hosted UI)
  allowed_oauth_flows                  = ["implicit", "code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  allowed_oauth_flows_user_pool_client = true

  # Callback URLs — update these once you know your frontend S3 website URL
  # You can run: terraform output frontend_url  to get the URL after deploy
  callback_urls = ["http://localhost:3000", "https://${aws_s3_bucket.frontend_bucket.bucket}.s3-website-${var.aws_region}.amazonaws.com"]
  logout_urls   = ["http://localhost:3000", "https://${aws_s3_bucket.frontend_bucket.bucket}.s3-website-${var.aws_region}.amazonaws.com"]

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",      # standard password auth
    "ALLOW_REFRESH_TOKEN_AUTH", # refresh tokens
    "ALLOW_USER_PASSWORD_AUTH", # simple username + password (easier for dev)
  ]
}

# ── Cognito Hosted UI Domain ──────────────────────────────────────────────────
# Provides a ready-made login page at:
# https://<domain>.auth.<region>.amazoncognito.com/login

resource "aws_cognito_user_pool_domain" "academy_domain" {
  domain       = "${local.name_prefix}-${local.account_id}"
  user_pool_id = aws_cognito_user_pool.academy_pool.id
}
