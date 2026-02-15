import { describe, it, expect, beforeEach } from "bun:test";
import { app } from "../../src/api/app";
import { runMigrations } from "../../src/db/migrate";
import { unlinkSync, existsSync } from "fs";

const TEST_DB = "./data/test-users-api.db";

describe("Users API", () => {
  beforeEach(() => {
    // Clean up test database
    if (existsSync(TEST_DB)) {
      unlinkSync(TEST_DB);
    }
    if (existsSync(`${TEST_DB}-shm`)) {
      unlinkSync(`${TEST_DB}-shm`);
    }
    if (existsSync(`${TEST_DB}-wal`)) {
      unlinkSync(`${TEST_DB}-wal`);
    }

    process.env.DATABASE_URL = TEST_DB;
    runMigrations(TEST_DB);
  });

  it("should list users", async () => {
    const res = await app.request("/api/users");
    expect(res.status).toBe(200);

    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);
  });

  it("should create a user", async () => {
    const res = await app.request("/api/users", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: "test@example.com",
        display_name: "Test User",
      }),
    });

    expect(res.status).toBe(200);

    const data = await res.json();
    expect(data.email).toBe("test@example.com");
    expect(data.id).toBeGreaterThan(0);
  });

  it("should reject duplicate email", async () => {
    // Create first user
    await app.request("/api/users", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: "test@example.com",
      }),
    });

    // Try to create duplicate
    const res = await app.request("/api/users", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: "test@example.com",
      }),
    });

    expect(res.status).toBe(409);

    const data = await res.json();
    expect(data.detail).toBe("User already exists");
  });
});
