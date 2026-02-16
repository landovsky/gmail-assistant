import { drizzle } from 'drizzle-orm/bun-sqlite';
import { Database } from 'bun:sqlite';
import { appConfig } from '../config/index.js';
import * as schema from './schema.js';

// Initialize database connection
const sqlite = new Database(
  appConfig.database.type === 'sqlite' ? appConfig.database.url : 'data/gmail-assistant.db',
  { strict: true }
);
sqlite.exec('PRAGMA journal_mode = WAL;');
sqlite.exec('PRAGMA foreign_keys = ON;');

export const db = drizzle(sqlite, { schema });
export { schema };

/** Accessor used by route modules */
export function getDb() {
  return db;
}
