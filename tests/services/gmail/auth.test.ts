// Gmail OAuth authentication tests
import { describe, test, before, after } from 'node:test';
import assert from 'node:assert';
import {
  loadCredentials,
  createOAuth2Client,
  isTokenExpired,
  saveToken,
  loadToken,
  type TokenData,
} from '../../../src/services/gmail/auth';
import { writeFileSync, unlinkSync, existsSync, mkdirSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

describe('Gmail OAuth Authentication', () => {
  const testDir = join(tmpdir(), `gmail-auth-test-${Date.now()}`);
  const testMasterKeyPath = join(testDir, 'master.key');
  const testTokenPath = join(testDir, 'token.json');

  before(() => {
    // Create test directory
    if (!existsSync(testDir)) {
      mkdirSync(testDir, { recursive: true });
    }

    // Create test master key
    writeFileSync(testMasterKeyPath, '59f2c1f7bcfef4def53eca144fa2eee3');

    // Backup and clear env var to test fallback
    if (!process.env.GOOGLE_CREDENTIALS_ENCRYPTED) {
      // If not set, we need to set it for tests
      // Using the actual value from .env for tests
      process.env.GOOGLE_CREDENTIALS_ENCRYPTED =
        '2f1XMi7Hcwb0Gd0gKq+8lwkQgxAMoDxOVyffCaVesCtvAMts1tiIv40ghz/cledw/trePHsUO23yEcISMkGd5aOXzUxllDE5/8nrVZ05nsGMi1jnnFN7g8veR07NTeTeuOblXAL9cFyHtQC9yUaLbOSQGhYTg9HVxSj/cF1p5CIVkMOO5uV9IThKGBqcexev5Dz4uJzss406+z0MjDt1gwLuHv0MJwe/8Cz8t5bX6T5TktAeIQyU+G9vhJysZuHprLC/yHXMJBo7gtxEwxGhwf5QgMoSjmMIWv7jnffI5+vYZaPnFAC8pmdYi3xbbKqcpBZPqLDDVO+Kq7aca0Kt5MJ16N0dADtw8VwAc0uxU02EH2ri7N3Atz486X/kmmCEnFRYZ4anypgplfuq1luaCwhDmnB+K2oPudq+nyeNoUnmOuZVm1hY2Kja/h0m7ZE5fhKffHY8WtqP0YFEUf6M2cdwokWlFC5WV77dkn5Ez6Y6I8Efxo5rNMvi--lC9A7He/cfhhAKhJ--sC560sKQkjmuGzJZrKXjEQ==';
    }
  });

  after(() => {
    // Cleanup
    if (existsSync(testTokenPath)) {
      unlinkSync(testTokenPath);
    }
    if (existsSync(testMasterKeyPath)) {
      unlinkSync(testMasterKeyPath);
    }
  });

  test('loadCredentials - decrypts from GOOGLE_CREDENTIALS_ENCRYPTED', () => {
    const credentials = loadCredentials(testMasterKeyPath);

    assert.ok(credentials);
    assert.ok(credentials.installed || credentials.web);

    const keys = credentials.installed || credentials.web;
    assert.ok(keys?.client_id);
    assert.ok(keys?.client_secret);
    assert.strictEqual(typeof keys?.client_id, 'string');
    assert.strictEqual(typeof keys?.client_secret, 'string');
  });

  test('createOAuth2Client - creates OAuth2 client from credentials', () => {
    const credentials = loadCredentials(testMasterKeyPath);
    const client = createOAuth2Client(credentials);

    assert.ok(client);
    assert.strictEqual(typeof client.generateAuthUrl, 'function');
    assert.strictEqual(typeof client.getToken, 'function');
  });

  test('isTokenExpired - detects expired tokens', () => {
    const expiredToken: TokenData = {
      access_token: 'test',
      scope: 'test',
      token_type: 'Bearer',
      expiry_date: Date.now() - 1000, // Expired 1 second ago
    };

    assert.strictEqual(isTokenExpired(expiredToken), true);
  });

  test('isTokenExpired - detects valid tokens', () => {
    const validToken: TokenData = {
      access_token: 'test',
      scope: 'test',
      token_type: 'Bearer',
      expiry_date: Date.now() + 3600 * 1000, // Expires in 1 hour
    };

    assert.strictEqual(isTokenExpired(validToken), false);
  });

  test('isTokenExpired - detects soon-to-expire tokens (within 5 min)', () => {
    const soonExpiredToken: TokenData = {
      access_token: 'test',
      scope: 'test',
      token_type: 'Bearer',
      expiry_date: Date.now() + 4 * 60 * 1000, // Expires in 4 minutes
    };

    assert.strictEqual(isTokenExpired(soonExpiredToken), true);
  });

  test('saveToken and loadToken - round trip', () => {
    const token: TokenData = {
      access_token: 'test_access_token',
      refresh_token: 'test_refresh_token',
      scope: 'https://www.googleapis.com/auth/gmail.modify',
      token_type: 'Bearer',
      expiry_date: Date.now() + 3600 * 1000,
    };

    saveToken(testTokenPath, token);

    const loaded = loadToken(testTokenPath);

    assert.ok(loaded);
    assert.strictEqual(loaded?.access_token, token.access_token);
    assert.strictEqual(loaded?.refresh_token, token.refresh_token);
    assert.strictEqual(loaded?.scope, token.scope);
    assert.strictEqual(loaded?.token_type, token.token_type);
    assert.strictEqual(loaded?.expiry_date, token.expiry_date);
  });

  test('loadToken - returns null for non-existent file', () => {
    const nonExistentPath = join(testDir, 'nonexistent-token.json');
    const loaded = loadToken(nonExistentPath);

    assert.strictEqual(loaded, null);
  });
});
