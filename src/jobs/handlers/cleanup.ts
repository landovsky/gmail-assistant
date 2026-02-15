import type { JobHandler } from "../types.js";
import type { Job, CleanupPayload } from "../types.js";
import { getAuthenticatedClient } from "../../services/gmail/auth.js";
import { GmailClient } from "../../services/gmail/client.js";
import { handleDoneRequested } from "../../workflows/index.js";
import { db } from "../../db/index.js";
import { emails, userLabels } from "../../db/schema.js";
import { eq } from "drizzle-orm";

export class CleanupHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as CleanupPayload;

    // Get email record
    const email = await db.query.emails.findFirst({
      where: eq(emails.id, payload.email_id),
    });

    if (!email) {
      throw new Error(`Email ${payload.email_id} not found`);
    }

    // Get authenticated Gmail client
    const oauth2Client = await getAuthenticatedClient(
      process.env.MASTER_KEY_PATH || "config/master.key",
      process.env.TOKEN_PATH || "config/token.json"
    );
    const client = new GmailClient(oauth2Client);

    // Load user's label mappings
    const labels = await db.query.userLabels.findMany({
      where: eq(userLabels.userId, email.userId),
    });

    const labelMappings = labels.map((l) => ({
      key: l.labelKey,
      name: l.gmailLabelName,
      gmailLabelId: l.gmailLabelId,
    }));

    // Handle Done label: archive thread and update status
    await handleDoneRequested({
      userId: email.userId,
      threadId: email.gmailThreadId,
      client,
      labelMappings,
    });

    console.log(`✓ Thread archived for email ${payload.email_id}: thread_id=${email.gmailThreadId}`);
  }
}
