import { Database } from "bun:sqlite";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export function runMigrations(dbPath: string) {
  const db = new Database(dbPath, { strict: true });
  db.exec("PRAGMA foreign_keys = ON;");

  // Check if migrations have already been applied by checking for users table
  const tableCheck = db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").get();

  if (tableCheck) {
    console.log("Database already migrated, skipping migrations");
    db.close();
    return;
  }

  const migrationPath = join(__dirname, "../../drizzle/0000_init.sql");
  const migration = readFileSync(migrationPath, "utf-8");

  db.exec(migration);
  console.log("Database migrations applied successfully");

  db.close();
}

// Run migrations if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  const dbPath = process.env.DATABASE_URL || "./data/gmail-assistant.db";
  runMigrations(dbPath);
}
