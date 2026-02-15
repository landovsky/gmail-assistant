// Gmail OAuth 2.0 authentication and credential management
import { google } from 'googleapis';
import { OAuth2Client } from 'google-auth-library';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { decryptCredentials } from '../../lib/encryption.js';
import http from 'http';
import { URL } from 'url';
import open from 'open';

const SCOPES = ['https://www.googleapis.com/auth/gmail.modify'];
const REDIRECT_PORT = 3001;
const REDIRECT_URI = `http://localhost:${REDIRECT_PORT}`;

export interface GoogleCredentials {
  installed?: {
    client_id: string;
    client_secret: string;
    redirect_uris: string[];
  };
  web?: {
    client_id: string;
    client_secret: string;
    redirect_uris: string[];
  };
}

export interface TokenData {
  access_token: string;
  refresh_token?: string;
  scope: string;
  token_type: string;
  expiry_date: number;
}

/**
 * Load Google OAuth credentials from encrypted environment variable or file
 */
export function loadCredentials(masterKeyPath: string): GoogleCredentials {
  // Try encrypted env var first
  const encryptedCreds = process.env.GOOGLE_CREDENTIALS_ENCRYPTED;
  if (encryptedCreds) {
    const masterKey = readFileSync(masterKeyPath, 'utf-8').trim();
    const decrypted = decryptCredentials(encryptedCreds, masterKey);

    // Parse YAML-like format from Rails credentials
    // Extract the google credentials section
    const googleMatch = decrypted.match(/google:\s*\n((?:\s+.+\n?)+)/);
    if (!googleMatch) {
      throw new Error('Google credentials not found in encrypted credentials');
    }

    const googleSection = googleMatch[1];
    const clientIdMatch = googleSection.match(/client_id:\s*(.+)/);
    const clientSecretMatch = googleSection.match(/client_secret:\s*(.+)/);

    if (!clientIdMatch || !clientSecretMatch) {
      throw new Error('Invalid Google credentials format in encrypted credentials');
    }

    return {
      installed: {
        client_id: clientIdMatch[1].trim(),
        client_secret: clientSecretMatch[1].trim(),
        redirect_uris: [REDIRECT_URI],
      },
    };
  }

  // Fallback to credentials file
  const credsPath = process.env.GMAIL_CREDENTIALS_PATH || 'config/credentials.json';
  if (!existsSync(credsPath)) {
    throw new Error(
      `Gmail credentials not found. Set GOOGLE_CREDENTIALS_ENCRYPTED or provide ${credsPath}`
    );
  }

  return JSON.parse(readFileSync(credsPath, 'utf-8'));
}

/**
 * Load token from file if it exists
 */
export function loadToken(tokenPath: string): TokenData | null {
  if (!existsSync(tokenPath)) {
    return null;
  }

  try {
    return JSON.parse(readFileSync(tokenPath, 'utf-8'));
  } catch (error) {
    console.warn(`Failed to load token from ${tokenPath}:`, error);
    return null;
  }
}

/**
 * Save token to file
 */
export function saveToken(tokenPath: string, token: TokenData): void {
  writeFileSync(tokenPath, JSON.stringify(token, null, 2));
  console.log(`✓ Token saved to ${tokenPath}`);
}

/**
 * Create OAuth2 client from credentials
 */
export function createOAuth2Client(credentials: GoogleCredentials): OAuth2Client {
  const keys = credentials.installed || credentials.web;
  if (!keys) {
    throw new Error('Invalid credentials format: missing installed or web keys');
  }

  return new google.auth.OAuth2(keys.client_id, keys.client_secret, REDIRECT_URI);
}

/**
 * Run browser-based OAuth consent flow
 * Opens browser, starts local server to receive callback, returns authorization code
 */
export async function runConsentFlow(oauth2Client: OAuth2Client): Promise<string> {
  const authUrl = oauth2Client.generateAuthUrl({
    access_type: 'offline',
    scope: SCOPES,
    prompt: 'consent', // Force consent to get refresh token
  });

  console.log('\n📧 Gmail Authorization Required');
  console.log('Opening browser for consent...');
  console.log('If browser does not open, visit this URL:');
  console.log(authUrl);
  console.log();

  // Open browser
  await open(authUrl);

  // Start local server to receive callback
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      if (!req.url) {
        return;
      }

      const url = new URL(req.url, REDIRECT_URI);
      const code = url.searchParams.get('code');
      const error = url.searchParams.get('error');

      if (error) {
        res.writeHead(400, { 'Content-Type': 'text/html' });
        res.end(`<h1>Authorization Failed</h1><p>Error: ${error}</p>`);
        server.close();
        reject(new Error(`OAuth error: ${error}`));
        return;
      }

      if (code) {
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(`
          <h1>Authorization Successful!</h1>
          <p>You can close this window and return to the terminal.</p>
        `);
        server.close();
        resolve(code);
        return;
      }

      res.writeHead(404);
      res.end('Not found');
    });

    server.listen(REDIRECT_PORT, () => {
      console.log(`Listening for OAuth callback on ${REDIRECT_URI}...`);
    });

    // Timeout after 5 minutes
    setTimeout(() => {
      server.close();
      reject(new Error('OAuth consent flow timed out after 5 minutes'));
    }, 5 * 60 * 1000);
  });
}

/**
 * Exchange authorization code for tokens
 */
export async function exchangeCodeForTokens(
  oauth2Client: OAuth2Client,
  code: string
): Promise<TokenData> {
  const { tokens } = await oauth2Client.getToken(code);

  if (!tokens.access_token) {
    throw new Error('No access token received from Google');
  }

  return {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    scope: tokens.scope || SCOPES.join(' '),
    token_type: tokens.token_type || 'Bearer',
    expiry_date: tokens.expiry_date || Date.now() + 3600 * 1000,
  };
}

/**
 * Check if token is expired or about to expire (within 5 minutes)
 */
export function isTokenExpired(token: TokenData): boolean {
  const expiryDate = token.expiry_date;
  const now = Date.now();
  const buffer = 5 * 60 * 1000; // 5 minutes

  return now + buffer >= expiryDate;
}

/**
 * Refresh access token using refresh token
 */
export async function refreshAccessToken(
  oauth2Client: OAuth2Client,
  token: TokenData
): Promise<TokenData> {
  if (!token.refresh_token) {
    throw new Error('No refresh token available - need to re-authorize');
  }

  oauth2Client.setCredentials({
    refresh_token: token.refresh_token,
  });

  const { credentials } = await oauth2Client.refreshAccessToken();

  return {
    access_token: credentials.access_token!,
    refresh_token: token.refresh_token, // Keep original refresh token
    scope: credentials.scope || token.scope,
    token_type: credentials.token_type || 'Bearer',
    expiry_date: credentials.expiry_date || Date.now() + 3600 * 1000,
  };
}

/**
 * Get authenticated OAuth2 client with valid token
 * Handles token loading, expiry checking, refresh, and consent flow
 */
export async function getAuthenticatedClient(
  masterKeyPath: string,
  tokenPath: string
): Promise<OAuth2Client> {
  const credentials = loadCredentials(masterKeyPath);
  const oauth2Client = createOAuth2Client(credentials);

  let token = loadToken(tokenPath);

  // If no token exists, run consent flow
  if (!token) {
    console.log('No token found, starting OAuth consent flow...');
    const code = await runConsentFlow(oauth2Client);
    token = await exchangeCodeForTokens(oauth2Client, code);
    saveToken(tokenPath, token);
  }

  // If token is expired, refresh it
  if (isTokenExpired(token)) {
    console.log('Token expired, refreshing...');
    try {
      token = await refreshAccessToken(oauth2Client, token);
      saveToken(tokenPath, token);
      console.log('✓ Token refreshed');
    } catch (error) {
      console.error('Failed to refresh token, re-running consent flow...');
      const code = await runConsentFlow(oauth2Client);
      token = await exchangeCodeForTokens(oauth2Client, code);
      saveToken(tokenPath, token);
    }
  }

  // Set credentials on client
  oauth2Client.setCredentials(token);

  return oauth2Client;
}

/**
 * Get user's Gmail email address from profile API
 */
export async function getUserEmail(oauth2Client: OAuth2Client): Promise<string> {
  const gmail = google.gmail({ version: 'v1', auth: oauth2Client });
  const profile = await gmail.users.getProfile({ userId: 'me' });

  if (!profile.data.emailAddress) {
    throw new Error('Failed to get user email from Gmail profile');
  }

  return profile.data.emailAddress;
}
