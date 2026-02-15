import Database from "better-sqlite3";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export function runMigrations(dbPath: string) {
  const db = new Database(dbPath);
  db.pragma("foreign_keys = ON");
  
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
