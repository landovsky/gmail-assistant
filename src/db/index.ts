import { drizzle } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import { appConfig } from '../config/index.js';
import * as schema from './schema.js';

// Initialize database connection
const sqlite = new Database(
  appConfig.database.type === 'sqlite' ? appConfig.database.url : 'data/gmail-assistant.db'
);
sqlite.pragma('journal_mode = WAL');
sqlite.pragma('foreign_keys = ON');

export const db = drizzle(sqlite, { schema });
export { schema };

/** Accessor used by route modules */
export function getDb() {
  return db;
}
