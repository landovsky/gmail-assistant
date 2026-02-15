import { describe, it, expect } from "bun:test";
import { app } from "../../src/api/app";

describe("Health API", () => {
  it("should return ok status", async () => {
    const res = await app.request("/api/health");
    expect(res.status).toBe(200);

    const data = await res.json();
    expect(data).toEqual({ status: "ok" });
  });
});
