/**
 * Admin Database Browser Routes
 * Simple read-only interface for viewing all database tables
 */

import { Hono } from "hono";
import { getDb, schema } from "../db/index.js";
import { AdminLayout } from "./pages/admin-layout.js";
import { TableListPage } from "./pages/table-list.js";
import { eq, sql, like } from "drizzle-orm";

export const adminRoutes = new Hono();
const db = getDb();

// Admin home - list all tables
adminRoutes.get("/", (c) => {
  const tables = [
    { name: "users", icon: "👤", description: "User accounts" },
    { name: "user_labels", icon: "🏷️", description: "Gmail label mappings" },
    { name: "user_settings", icon: "⚙️", description: "User configuration" },
    { name: "sync_state", icon: "🔄", description: "Gmail sync status" },
    { name: "emails", icon: "✉️", description: "Email records" },
    { name: "email_events", icon: "📜", description: "Lifecycle events" },
    { name: "llm_calls", icon: "🧠", description: "LLM API calls" },
    { name: "jobs", icon: "📋", description: "Background jobs" },
    { name: "agent_runs", icon: "🤖", description: "Agent executions" },
  ];

  return c.html(
    <AdminLayout title="Database Tables">
      <div style="padding: 2rem;">
        <h1 style="font-size: 1.8rem; margin-bottom: 2rem;">Database Tables</h1>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem;">
          {tables.map((table) => (
            <a href={`/admin/table/${table.name}`} style="text-decoration: none; color: inherit;">
              <div style="background: #1a1d27; border: 1px solid #2a2d37; border-radius: 8px; padding: 1.5rem; cursor: pointer; transition: all 0.2s;"
                   onmouseover="this.style.borderColor='#4a7c59'" onmouseout="this.style.borderColor='#2a2d37'">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">{table.icon}</div>
                <div style="font-size: 1.1rem; font-weight: bold; margin-bottom: 0.3rem;">{table.name}</div>
                <div style="font-size: 0.9rem; color: #999;">{table.description}</div>
              </div>
            </a>
          ))}
        </div>
      </div>
    </AdminLayout>
  );
});

// View table data
adminRoutes.get("/table/:tableName", async (c) => {
  const tableName = c.req.param("tableName");
  const page = parseInt(c.req.query("page") || "1");
  const limit = parseInt(c.req.query("limit") || "50");
  const search = c.req.query("search") || "";
  const offset = (page - 1) * limit;

  let data: any[] = [];
  let total = 0;
  let columns: string[] = [];

  try {
    switch (tableName) {
      case "users":
        {
          const query = db.select().from(schema.users).limit(limit).offset(offset);
          if (search) {
            query.where(like(schema.users.email, `%${search}%`));
          }
          data = await query;
          const countResult = await db.select({ count: sql<number>`count(*)` }).from(schema.users);
          total = countResult[0].count;
          columns = ["id", "email", "displayName", "isActive", "onboardedAt", "createdAt"];
        }
        break;

      case "user_labels":
        {
          data = await db.select().from(schema.userLabels).limit(limit).offset(offset);
          const countResult = await db.select({ count: sql<number>`count(*)` }).from(schema.userLabels);
          total = countResult[0].count;
          columns = ["userId", "labelKey", "gmailLabelId", "gmailLabelName"];
        }
        break;

      case "user_settings":
        {
          data = await db.select().from(schema.userSettings).limit(limit).offset(offset);
          const countResult = await db.select({ count: sql<number>`count(*)` }).from(schema.userSettings);
          total = countResult[0].count;
          columns = ["userId", "settingKey", "settingValue"];
        }
        break;

      case "sync_state":
        {
          data = await db.select().from(schema.syncState).limit(limit).offset(offset);
          const countResult = await db.select({ count: sql<number>`count(*)` }).from(schema.syncState);
          total = countResult[0].count;
          columns = ["userId", "lastHistoryId", "lastSyncAt", "watchExpiration"];
        }
        break;

      case "emails":
        {
          const query = db.select().from(schema.emails).limit(limit).offset(offset).orderBy(sql`id DESC`);
          if (search) {
            query.where(
              sql`${schema.emails.subject} LIKE ${`%${search}%`} OR ${schema.emails.senderEmail} LIKE ${`%${search}%`}`
            );
          }
          data = await query;
          const countResult = await db.select({ count: sql<number>`count(*)` }).from(schema.emails);
          total = countResult[0].count;
          columns = ["id", "userId", "subject", "senderEmail", "classification", "status", "confidence", "receivedAt"];
        }
        break;

      case "email_events":
        {
          data = await db.select().from(schema.emailEvents).limit(limit).offset(offset).orderBy(sql`id DESC`);
          const countResult = await db.select({ count: sql<number>`count(*)` }).from(schema.emailEvents);
          total = countResult[0].count;
          columns = ["id", "userId", "gmailThreadId", "eventType", "detail", "createdAt"];
        }
        break;

      case "llm_calls":
        {
          data = await db.select().from(schema.llmCalls).limit(limit).offset(offset).orderBy(sql`id DESC`);
          const countResult = await db.select({ count: sql<number>`count(*)` }).from(schema.llmCalls);
          total = countResult[0].count;
          columns = ["id", "userId", "gmailThreadId", "callType", "model", "totalTokens", "latencyMs", "createdAt"];
        }
        break;

      case "jobs":
        {
          data = await db.select().from(schema.jobs).limit(limit).offset(offset).orderBy(sql`id DESC`);
          const countResult = await db.select({ count: sql<number>`count(*)` }).from(schema.jobs);
          total = countResult[0].count;
          columns = ["id", "userId", "jobType", "status", "attempts", "errorMessage", "createdAt"];
        }
        break;

      case "agent_runs":
        {
          data = await db.select().from(schema.agentRuns).limit(limit).offset(offset).orderBy(sql`id DESC`);
          const countResult = await db.select({ count: sql<number>`count(*)` }).from(schema.agentRuns);
          total = countResult[0].count;
          columns = ["id", "userId", "gmailThreadId", "profile", "status", "iterations", "createdAt"];
        }
        break;

      default:
        return c.text("Table not found", 404);
    }

    const totalPages = Math.ceil(total / limit);

    return c.html(
      <TableListPage
        tableName={tableName}
        data={data}
        columns={columns}
        page={page}
        limit={limit}
        total={total}
        totalPages={totalPages}
        search={search}
      />
    );
  } catch (error) {
    return c.text(`Error loading table: ${error}`, 500);
  }
});

// View single record detail
adminRoutes.get("/table/:tableName/:id", async (c) => {
  const tableName = c.req.param("tableName");
  const id = parseInt(c.req.param("id"));

  let record: any = null;

  try {
    switch (tableName) {
      case "users":
        {
          const result = await db.select().from(schema.users).where(eq(schema.users.id, id)).limit(1);
          record = result[0];
        }
        break;
      case "emails":
        {
          const result = await db.select().from(schema.emails).where(eq(schema.emails.id, id)).limit(1);
          record = result[0];
        }
        break;
      case "email_events":
        {
          const result = await db.select().from(schema.emailEvents).where(eq(schema.emailEvents.id, id)).limit(1);
          record = result[0];
        }
        break;
      case "llm_calls":
        {
          const result = await db.select().from(schema.llmCalls).where(eq(schema.llmCalls.id, id)).limit(1);
          record = result[0];
        }
        break;
      case "jobs":
        {
          const result = await db.select().from(schema.jobs).where(eq(schema.jobs.id, id)).limit(1);
          record = result[0];
        }
        break;
      case "agent_runs":
        {
          const result = await db.select().from(schema.agentRuns).where(eq(schema.agentRuns.id, id)).limit(1);
          record = result[0];
        }
        break;
      default:
        return c.text("Table not found", 404);
    }

    if (!record) {
      return c.text("Record not found", 404);
    }

    return c.html(
      <AdminLayout title={`${tableName} #${id}`}>
        <div style="padding: 2rem;">
          <div style="margin-bottom: 1rem;">
            <a href={`/admin/table/${tableName}`} style="color: #4a7c59; text-decoration: none;">← Back to {tableName}</a>
          </div>
          <h1 style="font-size: 1.8rem; margin-bottom: 2rem;">{tableName} #{id}</h1>
          <div style="background: #1a1d27; border: 1px solid #2a2d37; border-radius: 8px; padding: 1.5rem;">
            <table style="width: 100%; border-collapse: collapse;">
              <tbody>
                {Object.entries(record).map(([key, value]) => (
                  <tr style="border-bottom: 1px solid #2a2d37;">
                    <td style="padding: 0.75rem; font-weight: bold; width: 200px; vertical-align: top;">{key}</td>
                    <td style="padding: 0.75rem; word-break: break-word;">
                      {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </AdminLayout>
    );
  } catch (error) {
    return c.text(`Error loading record: ${error}`, 500);
  }
});
