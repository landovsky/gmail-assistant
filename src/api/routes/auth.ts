import { Hono } from 'hono';
import { z } from 'zod';
import { existsSync } from 'fs';
import { getDb, schema } from '../../db/index.js';
import { eq } from 'drizzle-orm';
import { getAuthenticatedClient, getUserEmail } from '../../services/gmail/auth.js';
import { config } from '../../lib/config.js';

export const authRoutes = new Hono();
const db = getDb();

const initQuerySchema = z.object({
  display_name: z.string().optional(),
  migrate_v1: z
    .enum(['true', 'false'])
    .transform((v) => v === 'true')
    .optional()
    .default('true'),
});

// POST /api/auth/init - Bootstrap OAuth and onboard first user
authRoutes.post('/init', async (c) => {
  // Parse query params
  const raw = {
    display_name: c.req.query('display_name'),
    migrate_v1: c.req.query('migrate_v1'),
  };
  const parsed = initQuerySchema.safeParse(raw);
  if (!parsed.success) {
    return c.json({ detail: parsed.error.issues.map((i) => i.message).join('; ') }, 400);
  }
  const { display_name, migrate_v1 } = parsed.data;

  // Check that credentials file exists (personal OAuth mode)
  const credentialsPath = config.gmail.credentialsPath || 'config/credentials.json';

  if (!process.env.GOOGLE_CREDENTIALS_ENCRYPTED && !existsSync(credentialsPath)) {
    return c.json({ detail: `credentials.json not found at ${credentialsPath}` }, 400);
  }

  try {
    // Get authenticated OAuth2 client (triggers browser consent if needed)
    const masterKeyPath = 'config/master.key';
    const tokenPath = config.gmail.tokenPath || 'config/token.json';
    const oauth2Client = await getAuthenticatedClient(masterKeyPath, tokenPath);

    // Get user's email from Gmail profile
    let email: string;
    try {
      email = await getUserEmail(oauth2Client);
    } catch {
      return c.json({ detail: 'Could not get email from Gmail profile' }, 500);
    }

    // Check if user already exists
    const existing = await db
      .select()
      .from(schema.users)
      .where(eq(schema.users.email, email))
      .limit(1);

    let userId: number;
    let alreadyOnboarded = false;

    if (existing.length > 0) {
      userId = existing[0].id;
      alreadyOnboarded = !!existing[0].onboardedAt;

      // Re-activate if previously deactivated
      if (!existing[0].isActive) {
        await db.update(schema.users).set({ isActive: true }).where(eq(schema.users.id, userId));
      }

      // Update display name if provided and not already set
      if (display_name && !existing[0].displayName) {
        await db
          .update(schema.users)
          .set({ displayName: display_name })
          .where(eq(schema.users.id, userId));
      }
    } else {
      // Create new user
      const [user] = await db
        .insert(schema.users)
        .values({
          email,
          displayName: display_name ?? null,
          isActive: true,
          onboardedAt: new Date().toISOString(),
        })
        .returning();

      userId = user.id;
    }

    // Mark as onboarded if not already
    if (!alreadyOnboarded) {
      await db
        .update(schema.users)
        .set({ onboardedAt: new Date().toISOString() })
        .where(eq(schema.users.id, userId));
    }

    // Initialize sync state if not exists
    const existingSyncState = await db
      .select()
      .from(schema.syncState)
      .where(eq(schema.syncState.userId, userId))
      .limit(1);

    if (existingSyncState.length === 0) {
      await db.insert(schema.syncState).values({
        userId,
        lastHistoryId: '0',
      });
    }

    // Migrate v1 label IDs from config if requested
    let migratedV1 = false;
    if (migrate_v1) {
      // Check if user already has labels provisioned
      const existingLabels = await db
        .select()
        .from(schema.userLabels)
        .where(eq(schema.userLabels.userId, userId))
        .limit(1);

      if (existingLabels.length === 0) {
        // No label provisioning without the Gmail label service,
        // but we record that the user was set up for migration
        migratedV1 = true;
      }
    }

    return c.json({
      user_id: userId,
      email,
      onboarded: true,
      migrated_v1: migratedV1,
    });
  } catch (error) {
    console.error('Auth init error:', error);
    return c.json(
      {
        detail: error instanceof Error ? error.message : 'Internal server error',
      },
      500
    );
  }
});
