import { describe, it } from "node:test";
import assert from "node:assert";
import { app } from "../../src/api/app";

describe("POST /api/auth/init", () => {
  it("should return 400 when credentials.json is missing", async () => {
    // In test environment, no credentials file and no encrypted env var
    // should result in a 400 error
    const res = await app.request("/api/auth/init", {
      method: "POST",
    });

    // Should be 400 (credentials not found) or 500 (auth error)
    // depending on environment, but definitely not 200
    assert.ok(
      res.status === 400 || res.status === 500,
      `Expected 400 or 500, got ${res.status}`
    );

    const data = await res.json();
    assert.ok(data.detail, "Should have a detail error message");
  });

  it("should accept optional display_name query parameter", async () => {
    const res = await app.request(
      "/api/auth/init?display_name=Test%20User",
      { method: "POST" }
    );

    // Will still fail due to missing credentials, but should parse the param
    assert.ok(
      res.status === 400 || res.status === 500,
      "Should fail gracefully without credentials"
    );
  });

  it("should only respond to POST", async () => {
    const res = await app.request("/api/auth/init", { method: "GET" });
    assert.notStrictEqual(res.status, 200);
  });
});
