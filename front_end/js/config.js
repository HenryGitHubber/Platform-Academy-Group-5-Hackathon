/**
 * CONFIG.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Update the PRODUCTION values below after running:  terraform apply
 * Then run: terraform output   to print all the values you need.
 *
 * For LOCAL development (opening the HTML file in a browser), the defaults
 * below will work automatically — no changes needed.
 */

const IS_LOCAL =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1" ||
  window.location.protocol === "file:";

const CONFIG = {
  // ── Data URL ──────────────────────────────────────────────────────────────
  // Local:      uses the processed_all_data.json copied into front_end/
  // Production: replace with value from: terraform output processed_data_url
  DATA_URL: IS_LOCAL
    ? "processed_all_data.json"
    : "https://platform-academy-raw-data-group5.s3.us-east-1.amazonaws.com/processed/all_data.json",

  // ── Cognito ───────────────────────────────────────────────────────────────
  // Replace all three values below with output from: terraform apply
  COGNITO_REGION:       "REPLACE_WITH_TERRAFORM_OUTPUT_aws_region",
  COGNITO_USER_POOL_ID: "REPLACE_WITH_TERRAFORM_OUTPUT_cognito_user_pool_id",
  COGNITO_CLIENT_ID:    "REPLACE_WITH_TERRAFORM_OUTPUT_cognito_client_id",

  // ── Cognito Hosted UI domain ──────────────────────────────────────────────
  // Format: <domain-prefix>.auth.<region>.amazoncognito.com
  // Get the full login URL from: terraform output cognito_hosted_ui_url
  COGNITO_DOMAIN: "REPLACE_WITH_YOUR_COGNITO_DOMAIN",

  // ── Redirect URI ──────────────────────────────────────────────────────────
  // After Cognito login, it redirects back here.
  // For production, this must exactly match a callback URL in cognito.tf.
  REDIRECT_URI: IS_LOCAL
    ? window.location.origin + "/"
    : "REPLACE_WITH_TERRAFORM_OUTPUT_frontend_url",
};
