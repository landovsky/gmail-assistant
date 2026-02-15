import { drizzle } from "drizzle-orm/better-sqlite3";
import Database from "better-sqlite3";
import { appConfig } from "../config/index.js";
import * as schema from "./schema.js";

let db: ReturnType<typeof drizzle>;

export function getDb() {
  if (!db) {
    if (appConfig.database.type !== "sqlite") {
      throw new Error("Only SQLite is currently supported");
    }

    const sqlite = new Database(appConfig.database.url);
    sqlite.pragma("journal_mode = WAL");
    sqlite.pragma("foreign_keys = ON");

    db = drizzle(sqlite, { schema });
  }

  return db;
}

// Export db instance for convenience
export { db, schema };
