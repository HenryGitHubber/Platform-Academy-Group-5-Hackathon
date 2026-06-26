const express = require('express');
const cors    = require('cors');
const fs      = require('fs');
const path    = require('path');
const {
  QuickSightClient,
  GenerateEmbedUrlForRegisteredUserCommand,
  DescribeDashboardDefinitionCommand,
} = require('@aws-sdk/client-quicksight');
const { STSClient, GetCallerIdentityCommand }                         = require('@aws-sdk/client-sts');
const { SSOClient, GetRoleCredentialsCommand }                        = require('@aws-sdk/client-sso');
const { NodeHttpHandler }                                             = require('@smithy/node-http-handler');
const { HttpsProxyAgent }                                             = require('https-proxy-agent');

const app          = express();
const REGION       = 'us-east-1';
const ACCOUNT_ID   = '339713122290';
const ROLE_NAME    = 'CDHDevOps';
const QS_NS        = 'default';
const DASHBOARD_ID = '9d9c754b-7cdb-4c8e-b483-123a0e879c88';
const ALLOWED_ORIGINS = ['http://localhost:4200', 'http://localhost:4300'];

// ── Corporate proxy setup ─────────────────────────────────────────────────
const PROXY_URL = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
let requestHandler;
if (PROXY_URL) {
  console.log('Using corporate proxy:', PROXY_URL.replace(/:[^:@]+@/, ':***@'));
  // rejectUnauthorized:false bypasses SSL-inspection certificate errors
  const agent = new HttpsProxyAgent(PROXY_URL, { rejectUnauthorized: false });
  requestHandler = new NodeHttpHandler({
    httpsAgent: agent,
    httpAgent:  agent,
    requestTimeout:        25_000,   // 25 s — corporate proxy can be slow
    throwOnRequestTimeout: true,
  });
} else {
  console.log('No proxy configured — using direct connection');
  requestHandler = new NodeHttpHandler({ requestTimeout: 15_000, throwOnRequestTimeout: true });
}

app.use(cors({ origin: ALLOWED_ORIGINS }));

// ── Read the best (most-recently-expiring, not-yet-expired) SSO token ────
function getSSOAccessToken() {
  const cacheDir = path.join(
    process.env.HOME || process.env.USERPROFILE || '',
    '.aws', 'sso', 'cache'
  );

  let bestToken = null;
  let bestExpiry = new Date(0);

  for (const file of fs.readdirSync(cacheDir)) {
    if (!file.endsWith('.json')) continue;
    try {
      const data = JSON.parse(fs.readFileSync(path.join(cacheDir, file), 'utf8'));
      if (!data.accessToken || !data.expiresAt) continue;
      const expiry = new Date(data.expiresAt);
      if (expiry > new Date() && expiry > bestExpiry) {
        bestToken  = data.accessToken;
        bestExpiry = expiry;
      }
    } catch { /* skip unreadable files */ }
  }

  if (!bestToken) {
    throw new Error(
      'SSO token expired or not found. ' +
      'Please refresh your AWS session in VS Code AWS Toolkit (click the AWS icon → re-authenticate).'
    );
  }
  console.log('SSO token found, expires:', bestExpiry.toISOString());
  return bestToken;
}

// ── Exchange SSO token for temporary IAM credentials ─────────────────────
async function getCredentials() {
  // ── Option 1: env var credentials (set these if SSO is expired) ──────
  if (process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY) {
    console.log('Using env var credentials (AWS_ACCESS_KEY_ID)');
    return {
      accessKeyId:     process.env.AWS_ACCESS_KEY_ID,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      sessionToken:    process.env.AWS_SESSION_TOKEN,
    };
  }

  // ── Option 2: SSO cache ────────────────────────────────────────────────
  const accessToken = getSSOAccessToken();
  const sso = new SSOClient({
    region: REGION,
    requestHandler,
  });

  let result;
  try {
    result = await sso.send(new GetRoleCredentialsCommand({
      accessToken,
      accountId: ACCOUNT_ID,
      roleName:  ROLE_NAME,
    }));
  } catch (ssoErr) {
    if (ssoErr.name === 'UnauthorizedException' || ssoErr.name === 'ForbiddenException') {
      throw new Error(
        'SSO session expired. Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN ' +
        'env vars from https://view.awsapps.com/start and restart this proxy.'
      );
    }
    throw ssoErr;
  }

  const rc = result.roleCredentials;
  return {
    accessKeyId:     rc.accessKeyId,
    secretAccessKey: rc.secretAccessKey,
    sessionToken:    rc.sessionToken,
  };
}

// ── Shared: resolve credentials + build QS client + user ARN ────────────
async function buildQSContext() {
  const credentials = await getCredentials();
  console.log('Got credentials for', ACCOUNT_ID + '/' + ROLE_NAME);

  const sts      = new STSClient({ region: REGION, credentials, requestHandler });
  const identity = await sts.send(new GetCallerIdentityCommand({}));
  const parts    = identity.Arn.split(':');
  const rolePart = parts[5].split('/');
  const userArn  = `arn:aws:quicksight:${REGION}:${ACCOUNT_ID}:user/${QS_NS}/${rolePart[1]}/${rolePart[2]}`;
  console.log('QuickSight user ARN:', userArn);

  const qs = new QuickSightClient({ region: REGION, credentials, requestHandler });
  return { qs, userArn };
}

// ── /describe-dashboard — returns all sheet + visual IDs ─────────────────
// GET /describe-dashboard?dashboardId=OPTIONAL
app.get('/describe-dashboard', async (req, res) => {
  try {
    const dashboardId = req.query.dashboardId || DASHBOARD_ID;
    const { qs } = await buildQSContext();
    const response = await qs.send(new DescribeDashboardDefinitionCommand({
      AwsAccountId: ACCOUNT_ID,
      DashboardId:  dashboardId,
    }));

    // Extract sheet → visual mapping
    const sheets = (response.Definition?.Sheets || []).map(sheet => ({
      sheetId:   sheet.SheetId,
      sheetName: sheet.Name || sheet.SheetId,
      visuals:   (sheet.Visuals || []).map(v => {
        // Visual is a union type — find the first non-null key
        const typeKey  = Object.keys(v).find(k => v[k] && v[k].VisualId);
        const visual   = typeKey ? v[typeKey] : null;
        return {
          visualId:   visual?.VisualId   || null,
          title:      visual?.Title?.FormatText?.PlainText
                   || visual?.Title?.FormatText?.RichText
                   || typeKey || 'Untitled',
          type:       typeKey,
        };
      }).filter(v => v.visualId),
    }));

    console.log('Described dashboard:', dashboardId, '- sheets:', sheets.length);
    res.json({ dashboardId, sheets });
  } catch (err) {
    console.error('Error:', err.name, '-', err.message);
    res.status(500).json({ error: err.message, code: err.name });
  }
});

// ── /embed-dashboard — full dashboard embed URL ───────────────────────────
// GET /embed-dashboard?dashboardId=OPTIONAL
app.get('/embed-dashboard', async (req, res) => {
  try {
    const dashboardId = req.query.dashboardId || DASHBOARD_ID;
    const { qs, userArn } = await buildQSContext();
    const response = await qs.send(new GenerateEmbedUrlForRegisteredUserCommand({
      AwsAccountId:             ACCOUNT_ID,
      SessionLifetimeInMinutes: 120,
      UserArn:                  userArn,
      ExperienceConfiguration: {
        Dashboard: { InitialDashboardId: dashboardId },
      },
      AllowedDomains: ALLOWED_ORIGINS,
    }));
    console.log('Dashboard embed URL generated:', dashboardId);
    res.json({ url: response.EmbedUrl });
  } catch (err) {
    console.error('Error:', err.name, '-', err.message);
    res.status(500).json({ error: err.message, code: err.name });
  }
});

// ── /embed-visual — single chart embed URL ────────────────────────────────
// GET /embed-visual?dashboardId=X&sheetId=Y&visualId=Z
app.get('/embed-visual', async (req, res) => {
  const { dashboardId = DASHBOARD_ID, sheetId, visualId } = req.query;
  if (!sheetId || !visualId) {
    return res.status(400).json({ error: 'sheetId and visualId are required. Call /describe-dashboard first.' });
  }
  try {
    const { qs, userArn } = await buildQSContext();
    const response = await qs.send(new GenerateEmbedUrlForRegisteredUserCommand({
      AwsAccountId:             ACCOUNT_ID,
      SessionLifetimeInMinutes: 120,
      UserArn:                  userArn,
      ExperienceConfiguration: {
        DashboardVisual: {
          InitialDashboardVisualId: { DashboardId: dashboardId, SheetId: sheetId, VisualId: visualId },
        },
      },
      AllowedDomains: ALLOWED_ORIGINS,
    }));
    console.log('Visual embed URL generated:', visualId);
    res.json({ url: response.EmbedUrl });
  } catch (err) {
    console.error('Error:', err.name, '-', err.message);
    res.status(500).json({ error: err.message, code: err.name });
  }
});

// ── /embed-url — Amazon Q Search Bar (kept for Q chat widget) ────────────
app.get('/embed-url', async (req, res) => {
  try {
    const { qs, userArn } = await buildQSContext();
    const response = await qs.send(new GenerateEmbedUrlForRegisteredUserCommand({
      AwsAccountId:             ACCOUNT_ID,
      SessionLifetimeInMinutes: 120,
      UserArn:                  userArn,
      ExperienceConfiguration: { QSearchBar: {} },
      AllowedDomains:           ALLOWED_ORIGINS,
    }));
    console.log('Q Search Bar embed URL generated');
    res.json({ url: response.EmbedUrl });
  } catch (err) {
    console.error('Error:', err.name, '-', err.message);
    res.status(500).json({ error: err.message, code: err.name });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`\n✅ QuickSight embed proxy running on http://localhost:${PORT}`);
  console.log(`   Using SSO credentials: account=${ACCOUNT_ID}, role=${ROLE_NAME}`);
  console.log(`   Angular dev server expected on http://localhost:4200\n`);
});
