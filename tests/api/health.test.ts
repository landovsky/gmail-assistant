import { describe, it } from "node:test";
import assert from "node:assert";
import { app } from "../../src/api/app";

describe("Health API", () => {
  it("should return ok status", async () => {
    const res = await app.request("/api/health");
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.deepStrictEqual(data, { status: "ok" });
  });

  it("should return JSON content type", async () => {
    const res = await app.request("/api/health");
    assert.ok(res.headers.get("content-type")?.includes("application/json"));
  });

  it("should not require authentication", async () => {
    // Health endpoint should work without any auth headers
    const res = await app.request("/api/health");
    assert.strictEqual(res.status, 200);
  });

  it("should respond to GET only", async () => {
    const res = await app.request("/api/health", { method: "POST" });
    // Hono returns 404 for unmatched method/path combos
    assert.notStrictEqual(res.status, 200);
  });
});
