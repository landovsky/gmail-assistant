import { Hono } from 'hono';
import { z } from 'zod';
import { getDb, schema } from '../../db/index.js';
import { eq, and, sql } from 'drizzle-orm';

export const userRoutes = new Hono();
const db = getDb();

// --- Zod schemas for input validation ---

const createUserSchema = z.object({
  email: z.string().email(),
  display_name: z.string().optional(),
});

const updateSettingSchema = z.object({
  key: z.string().min(1),
  value: z.unknown(),
});

// --- Routes ---

// GET /api/users - List all active users
userRoutes.get('/', async (c) => {
  const users = await db
    .select({
      id: schema.users.id,
      email: schema.users.email,
      display_name: schema.users.displayName,
      onboarded_at: schema.users.onboardedAt,
    })
    .from(schema.users)
    .where(eq(schema.users.isActive, true));

  return c.json(users);
});

// POST /api/users - Create a new user
userRoutes.post('/', async (c) => {
  const body = await c.req.json();
  const parsed = createUserSchema.safeParse(body);

  if (!parsed.success) {
    return c.json({ detail: parsed.error.issues.map((i) => i.message).join('; ') }, 400);
  }

  const { email, display_name } = parsed.data;

  // Check for existing user
  const existing = await db
    .select({ id: schema.users.id })
    .from(schema.users)
    .where(eq(schema.users.email, email))
    .limit(1);

  if (existing.length > 0) {
    return c.json({ detail: 'User already exists' }, 409);
  }

  const [user] = await db
    .insert(schema.users)
    .values({
      email,
      displayName: display_name ?? null,
    })
    .returning({ id: schema.users.id, email: schema.users.email });

  return c.json({ id: user.id, email: user.email });
});

// GET /api/users/:user_id/settings - Get all settings for a user
userRoutes.get('/:user_id/settings', async (c) => {
  const userId = parseInt(c.req.param('user_id'));

  if (isNaN(userId)) {
    return c.json({ detail: 'Invalid user_id' }, 400);
  }

  // Verify user exists
  const user = await db
    .select({ id: schema.users.id })
    .from(schema.users)
    .where(eq(schema.users.id, userId))
    .limit(1);

  if (user.length === 0) {
    return c.json({ detail: `User ${userId} not found` }, 404);
  }

  const settings = await db
    .select({
      key: schema.userSettings.settingKey,
      value: schema.userSettings.settingValue,
    })
    .from(schema.userSettings)
    .where(eq(schema.userSettings.userId, userId));

  // Return as key-value map
  const result: Record<string, string> = {};
  for (const s of settings) {
    result[s.key] = s.value;
  }

  return c.json(result);
});

// PUT /api/users/:user_id/settings - Update a single user setting
userRoutes.put('/:user_id/settings', async (c) => {
  const userId = parseInt(c.req.param('user_id'));

  if (isNaN(userId)) {
    return c.json({ detail: 'Invalid user_id' }, 400);
  }

  const body = await c.req.json();
  const parsed = updateSettingSchema.safeParse(body);

  if (!parsed.success) {
    return c.json({ detail: parsed.error.issues.map((i) => i.message).join('; ') }, 400);
  }

  // Verify user exists
  const user = await db
    .select({ id: schema.users.id })
    .from(schema.users)
    .where(eq(schema.users.id, userId))
    .limit(1);

  if (user.length === 0) {
    return c.json({ detail: `User ${userId} not found` }, 404);
  }

  const { key, value } = parsed.data;
  const valueStr = typeof value === 'string' ? value : JSON.stringify(value);

  // Upsert: insert or update on conflict
  const existing = await db
    .select()
    .from(schema.userSettings)
    .where(and(eq(schema.userSettings.userId, userId), eq(schema.userSettings.settingKey, key)))
    .limit(1);

  if (existing.length > 0) {
    await db
      .update(schema.userSettings)
      .set({ settingValue: valueStr })
      .where(and(eq(schema.userSettings.userId, userId), eq(schema.userSettings.settingKey, key)));
  } else {
    await db.insert(schema.userSettings).values({
      userId,
      settingKey: key,
      settingValue: valueStr,
    });
  }

  return c.json({ ok: true });
});

// GET /api/users/:user_id/labels - Get Gmail labels for a user
userRoutes.get('/:user_id/labels', async (c) => {
  const userId = parseInt(c.req.param('user_id'));

  if (isNaN(userId)) {
    return c.json({ detail: 'Invalid user_id' }, 400);
  }

  // Verify user exists
  const user = await db
    .select({ id: schema.users.id })
    .from(schema.users)
    .where(eq(schema.users.id, userId))
    .limit(1);

  if (user.length === 0) {
    return c.json({ detail: `User ${userId} not found` }, 404);
  }

  const labels = await db
    .select({
      key: schema.userLabels.labelKey,
      gmail_label_id: schema.userLabels.gmailLabelId,
    })
    .from(schema.userLabels)
    .where(eq(schema.userLabels.userId, userId));

  // Return as key-value map
  const result: Record<string, string> = {};
  for (const l of labels) {
    result[l.key] = l.gmail_label_id;
  }

  return c.json(result);
});

// GET /api/users/:user_id/emails - Get emails for a user with optional filtering
userRoutes.get('/:user_id/emails', async (c) => {
  const userId = parseInt(c.req.param('user_id'));

  if (isNaN(userId)) {
    return c.json({ detail: 'Invalid user_id' }, 400);
  }

  // Verify user exists
  const user = await db
    .select({ id: schema.users.id })
    .from(schema.users)
    .where(eq(schema.users.id, userId))
    .limit(1);

  if (user.length === 0) {
    return c.json({ detail: `User ${userId} not found` }, 404);
  }

  const status = c.req.query('status');
  const classification = c.req.query('classification');

  const conditions = [eq(schema.emails.userId, userId)];

  if (status) {
    conditions.push(eq(schema.emails.status, status as any));
  } else if (!classification) {
    // Default: return pending emails if no filters specified
    conditions.push(eq(schema.emails.status, 'pending'));
  }

  if (classification) {
    conditions.push(eq(schema.emails.classification, classification as any));
  }

  const emails = await db
    .select({
      id: schema.emails.id,
      gmail_thread_id: schema.emails.gmailThreadId,
      gmail_message_id: schema.emails.gmailMessageId,
      subject: schema.emails.subject,
      sender_email: schema.emails.senderEmail,
      sender_name: schema.emails.senderName,
      snippet: schema.emails.snippet,
      classification: schema.emails.classification,
      status: schema.emails.status,
      confidence: schema.emails.confidence,
      received_at: schema.emails.receivedAt,
      processed_at: schema.emails.processedAt,
      drafted_at: schema.emails.draftedAt,
      acted_at: schema.emails.actedAt,
    })
    .from(schema.emails)
    .where(and(...conditions))
    .orderBy(sql`${schema.emails.id} DESC`);

  return c.json(emails);
});
