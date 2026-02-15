/**
 * Test Setup Configuration
 * Sets up test environment with in-memory database
 */

import { mkdirSync, writeFileSync } from 'fs';
import { join } from 'path';

// Ensure test data and config directories exist
const testDataDir = join(process.cwd(), 'data');
const configDir = join(process.cwd(), 'config');

try {
  mkdirSync(testDataDir, { recursive: true });
  mkdirSync(configDir, { recursive: true });
} catch (err) {
  // Directories already exist, ignore
}

// Create minimal test config
const testConfig = `
database:
  type: sqlite
  url: data/test.db

jobQueue:
  type: sqlite
  sqlitePath: data/test-jobs.db
  concurrency: 1

auth:
  masterKeyPath: config/test-master.key
  tokenPath: config/test-token.json

llm:
  defaultProvider: anthropic
  models:
    classify: claude-3-haiku-20240307
    draft: claude-3-5-sonnet-20241022
    context: claude-3-haiku-20240307

gmail:
  syncIntervalMs: 900000
  watchExpirationMs: 604800000
  maxHistoryResults: 100
`;

const testConfigPath = join(configDir, 'test.yml');
try {
  writeFileSync(testConfigPath, testConfig);
} catch (err) {
  // Config file already exists or cannot be written
}

// Set test environment
process.env.NODE_ENV = 'test';
process.env.CONFIG_PATH = testConfigPath;
