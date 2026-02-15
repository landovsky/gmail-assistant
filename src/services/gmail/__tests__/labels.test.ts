/**
 * Gmail Label Service Tests
 */

import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { drizzle } from "drizzle-orm/better-sqlite3";
import Database from "better-sqlite3";
import { migrate } from "drizzle-orm/better-sqlite3/migrator";
import * as schema from "../../../db/schema.js";
import { GmailLabelService, AI_LABELS } from "../labels.js";
import { clearDatabase, createTestUser } from "../../../db/seeds/test-helpers.js";

// Mock googleapis
const mockGmail = {
  users: {
    labels: {
      list: vi.fn(),
      create: vi.fn(),
    },
    messages: {
      modify: vi.fn(),
      batchModify: vi.fn(),
    },
  },
};

vi.mock("googleapis", () => ({
  google: {
    gmail: () => mockGmail,
  },
}));

// Mock getDb to return test database
const sqlite = new Database(":memory:");
sqlite.pragma("foreign_keys = ON");
const db = drizzle(sqlite, { schema });

vi.mock("../../../db/index.js", () => ({
  getDb: () => db,
}));

beforeEach(() => {
  migrate(db, { migrationsFolder: "./drizzle" });
  vi.clearAllMocks();
});

afterEach(() => {
  clearDatabase(db);
});

describe("GmailLabelService", () => {
  describe("provisionLabels", () => {
    test("should create all 9 AI labels for new user", async () => {
      const user = createTestUser(db);
      const labelService = new GmailLabelService({}, "me");

      // Mock Gmail API responses
      mockGmail.users.labels.list.mockResolvedValue({
        data: { labels: [] }, // No existing labels
      });

      let labelCount = 0;
      mockGmail.users.labels.create.mockImplementation(async ({ requestBody }: any) => {
        labelCount++;
        return {
          data: {
            id: `Label_${labelCount}`,
            name: requestBody.name,
          },
        };
      });

      await labelService.provisionLabels(user.id);

      // Verify all 9 labels were created
      expect(mockGmail.users.labels.create).toHaveBeenCalledTimes(9);

      // Verify database has all mappings
      const dbLabels = await db
        .select()
        .from(schema.userLabels)
        .where(schema.eq(schema.userLabels.userId, user.id))
        .all();

      expect(dbLabels).toHaveLength(9);

      // Verify label keys match
      const labelKeys = dbLabels.map((l) => l.labelKey).sort();
      const expectedKeys = Object.keys(AI_LABELS).sort();
      expect(labelKeys).toEqual(expectedKeys);
    });

    test("should not create duplicate labels if already exist in Gmail", async () => {
      const user = createTestUser(db);
      const labelService = new GmailLabelService({}, "me");

      // Mock existing labels in Gmail
      mockGmail.users.labels.list.mockResolvedValue({
        data: {
          labels: [
            { id: "Label_123", name: "🤖 AI" },
            { id: "Label_456", name: "🤖 AI/Needs Response" },
          ],
        },
      });

      mockGmail.users.labels.create.mockImplementation(async ({ requestBody }: any) => {
        return {
          data: {
            id: `Label_${Date.now()}`,
            name: requestBody.name,
          },
        };
      });

      await labelService.provisionLabels(user.id);

      // Should create only 7 labels (9 total - 2 existing)
      expect(mockGmail.users.labels.create).toHaveBeenCalledTimes(7);

      // Database should have all 9
      const dbLabels = await db
        .select()
        .from(schema.userLabels)
        .where(schema.eq(schema.userLabels.userId, user.id))
        .all();

      expect(dbLabels).toHaveLength(9);
    });

    test("should be idempotent - skip labels already in database", async () => {
      const user = createTestUser(db);
      const labelService = new GmailLabelService({}, "me");

      // Pre-populate some labels in database
      await db.insert(schema.userLabels).values([
        {
          userId: user.id,
          labelKey: "ai_parent",
          gmailLabelId: "Label_999",
          gmailLabelName: "🤖 AI",
        },
        {
          userId: user.id,
          labelKey: "needs_response",
          gmailLabelId: "Label_998",
          gmailLabelName: "🤖 AI/Needs Response",
        },
      ]);

      mockGmail.users.labels.list.mockResolvedValue({
        data: { labels: [] },
      });

      mockGmail.users.labels.create.mockImplementation(async ({ requestBody }: any) => {
        return {
          data: {
            id: `Label_${Date.now()}`,
            name: requestBody.name,
          },
        };
      });

      await labelService.provisionLabels(user.id);

      // Should only create 7 labels (9 - 2 in DB)
      expect(mockGmail.users.labels.create).toHaveBeenCalledTimes(7);

      // Database should still have 9 total
      const dbLabels = await db
        .select()
        .from(schema.userLabels)
        .where(schema.eq(schema.userLabels.userId, user.id))
        .all();

      expect(dbLabels).toHaveLength(9);
    });
  });

  describe("getLabelId", () => {
    test("should return Gmail label ID for existing label", async () => {
      const user = createTestUser(db);
      const labelService = new GmailLabelService({}, "me");

      await db.insert(schema.userLabels).values({
        userId: user.id,
        labelKey: "needs_response",
        gmailLabelId: "Label_123",
        gmailLabelName: "🤖 AI/Needs Response",
      });

      const labelId = await labelService.getLabelId(user.id, "needs_response");

      expect(labelId).toBe("Label_123");
    });

    test("should return null for non-existent label", async () => {
      const user = createTestUser(db);
      const labelService = new GmailLabelService({}, "me");

      const labelId = await labelService.getLabelId(user.id, "needs_response");

      expect(labelId).toBeNull();
    });
  });

  describe("getUserLabels", () => {
    test("should return all labels for user", async () => {
      const user = createTestUser(db);
      const labelService = new GmailLabelService({}, "me");

      await db.insert(schema.userLabels).values([
        {
          userId: user.id,
          labelKey: "needs_response",
          gmailLabelId: "Label_1",
          gmailLabelName: "🤖 AI/Needs Response",
        },
        {
          userId: user.id,
          labelKey: "outbox",
          gmailLabelId: "Label_2",
          gmailLabelName: "🤖 AI/Outbox",
        },
      ]);

      const labels = await labelService.getUserLabels(user.id);

      expect(labels).toHaveLength(2);
      expect(labels[0].labelKey).toBe("needs_response");
      expect(labels[1].labelKey).toBe("outbox");
    });
  });

  describe("addLabel", () => {
    test("should add label to message", async () => {
      const labelService = new GmailLabelService({}, "me");

      mockGmail.users.messages.modify.mockResolvedValue({});

      await labelService.addLabel("msg_123", "Label_456");

      expect(mockGmail.users.messages.modify).toHaveBeenCalledWith({
        userId: "me",
        id: "msg_123",
        requestBody: {
          addLabelIds: ["Label_456"],
        },
      });
    });
  });

  describe("removeLabel", () => {
    test("should remove label from message", async () => {
      const labelService = new GmailLabelService({}, "me");

      mockGmail.users.messages.modify.mockResolvedValue({});

      await labelService.removeLabel("msg_123", "Label_456");

      expect(mockGmail.users.messages.modify).toHaveBeenCalledWith({
        userId: "me",
        id: "msg_123",
        requestBody: {
          removeLabelIds: ["Label_456"],
        },
      });
    });
  });

  describe("batchModifyLabels", () => {
    test("should batch modify multiple messages", async () => {
      const labelService = new GmailLabelService({}, "me");

      mockGmail.users.messages.batchModify.mockResolvedValue({});

      await labelService.batchModifyLabels(
        ["msg_1", "msg_2", "msg_3"],
        ["Label_Add"],
        ["Label_Remove"]
      );

      expect(mockGmail.users.messages.batchModify).toHaveBeenCalledWith({
        userId: "me",
        requestBody: {
          ids: ["msg_1", "msg_2", "msg_3"],
          addLabelIds: ["Label_Add"],
          removeLabelIds: ["Label_Remove"],
        },
      });
    });

    test("should skip if no messages provided", async () => {
      const labelService = new GmailLabelService({}, "me");

      await labelService.batchModifyLabels([], ["Label_Add"]);

      expect(mockGmail.users.messages.batchModify).not.toHaveBeenCalled();
    });
  });

  describe("moveToLabel", () => {
    test("should move email to target label and remove others", async () => {
      const user = createTestUser(db);
      const labelService = new GmailLabelService({}, "me");

      // Set up user labels
      await db.insert(schema.userLabels).values([
        {
          userId: user.id,
          labelKey: "needs_response",
          gmailLabelId: "Label_1",
          gmailLabelName: "🤖 AI/Needs Response",
        },
        {
          userId: user.id,
          labelKey: "action_required",
          gmailLabelId: "Label_2",
          gmailLabelName: "🤖 AI/Action Required",
        },
        {
          userId: user.id,
          labelKey: "fyi",
          gmailLabelId: "Label_3",
          gmailLabelName: "🤖 AI/FYI",
        },
        {
          userId: user.id,
          labelKey: "outbox",
          gmailLabelId: "Label_4",
          gmailLabelName: "🤖 AI/Outbox",
        },
      ]);

      mockGmail.users.messages.modify.mockResolvedValue({});

      await labelService.moveToLabel(user.id, "msg_123", "action_required");

      expect(mockGmail.users.messages.modify).toHaveBeenCalledWith({
        userId: "me",
        id: "msg_123",
        requestBody: {
          addLabelIds: ["Label_2"], // action_required
          removeLabelIds: ["Label_1", "Label_3"], // needs_response, fyi (not outbox)
        },
      });
    });

    test("should throw error if target label not found", async () => {
      const user = createTestUser(db);
      const labelService = new GmailLabelService({}, "me");

      await expect(
        labelService.moveToLabel(user.id, "msg_123", "nonexistent")
      ).rejects.toThrow();
    });
  });
});
