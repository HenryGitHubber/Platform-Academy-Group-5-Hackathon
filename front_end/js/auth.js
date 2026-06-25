/**
 * AUTH.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Handles Cognito Hosted UI authentication using the OAuth2 implicit flow.
 * No external libraries required — pure vanilla JS.
 *
 * Flow:
 *  1. User clicks "Sign In"  →  redirected to Cognito Hosted UI
 *  2. After login, Cognito redirects back with tokens in the URL hash
 *  3. Tokens are stored in sessionStorage (cleared when browser tab closes)
 *  4. requireAuth() on any page checks the token before rendering
 */

const auth = (() => {
  const TOKEN_KEY = "pa_id_token";
  const EXPIRY_KEY = "pa_token_expiry";

  // ── Decode a JWT payload (no signature verification — client-side only) ──
  function _decodeJwt(token) {
    try {
      const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      return JSON.parse(window.atob(base64));
    } catch {
      return null;
    }
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Redirect the user to the Cognito Hosted UI login page.
   */
  function login() {
    // Skip auth entirely when running locally — go straight to dashboard
    if (IS_LOCAL) {
      window.location.href = "dashboard.html";
      return;
    }

    const loginUrl =
      `https://${CONFIG.COGNITO_DOMAIN}/login` +
      `?client_id=${CONFIG.COGNITO_CLIENT_ID}` +
      `&response_type=token` +
      `&scope=email+openid+profile` +
      `&redirect_uri=${encodeURIComponent(CONFIG.REDIRECT_URI)}`;

    window.location.href = loginUrl;
  }

  /**
   * Parse tokens from the URL hash after Cognito redirects back.
   * Call this on the page that Cognito redirects to (index.html).
   * Returns true if a valid token was found and stored.
   */
  function handleCallback() {
    const hash = window.location.hash.substring(1);
    if (!hash) return false;

    const params = Object.fromEntries(
      hash.split("&").map((p) => p.split("=").map(decodeURIComponent))
    );

    const idToken = params["id_token"];
    if (!idToken) return false;

    const payload = _decodeJwt(idToken);
    if (!payload) return false;

    sessionStorage.setItem(TOKEN_KEY, idToken);
    sessionStorage.setItem(EXPIRY_KEY, payload.exp.toString());

    // Clean the tokens out of the URL for security
    window.history.replaceState(null, "", window.location.pathname);
    return true;
  }

  /**
   * Returns true if the user has a valid, non-expired token.
   */
  function isAuthenticated() {
    if (IS_LOCAL) return true; // skip auth in local dev

    const token = sessionStorage.getItem(TOKEN_KEY);
    const expiry = sessionStorage.getItem(EXPIRY_KEY);
    if (!token || !expiry) return false;

    // Check token has not expired (expiry is Unix timestamp in seconds)
    return Date.now() / 1000 < parseInt(expiry, 10);
  }

  /**
   * If not authenticated, redirect to login. Call at the top of dashboard.html.
   */
  function requireAuth() {
    if (!isAuthenticated()) {
      window.location.href = "index.html";
    }
  }

  /**
   * Returns the decoded user info from the stored id_token.
   */
  function getUser() {
    if (IS_LOCAL) return { email: "dev@localhost", name: "Developer" };
    const token = sessionStorage.getItem(TOKEN_KEY);
    return token ? _decodeJwt(token) : null;
  }

  /**
   * Clear the session and redirect to login.
   */
  function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(EXPIRY_KEY);

    if (IS_LOCAL) {
      window.location.href = "index.html";
      return;
    }

    const logoutUrl =
      `https://${CONFIG.COGNITO_DOMAIN}/logout` +
      `?client_id=${CONFIG.COGNITO_CLIENT_ID}` +
      `&logout_uri=${encodeURIComponent(CONFIG.REDIRECT_URI)}`;

    window.location.href = logoutUrl;
  }

  return { login, handleCallback, isAuthenticated, requireAuth, getUser, logout };
})();
