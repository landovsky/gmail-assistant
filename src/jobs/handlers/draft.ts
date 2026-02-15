import type { JobHandler } from "../types.js";
import type { Job, DraftPayload } from "../types.js";
import { getAuthenticatedClient } from "../../services/gmail/auth.js";
import { GmailClient } from "../../services/gmail/client.js";
import { generateEmailDraft as generateDraft } from "../../services/drafting/engine.js";
import { handleDraftCreated } from "../../workflows/index.js";
import { db } from "../../db/index.js";
import { emails, userLabels } from "../../db/schema.js";
import { eq } from "drizzle-orm";

export class DraftHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as DraftPayload;

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
      name: l.labelName,
      gmailLabelId: l.gmailLabelId,
    }));

    // Generate draft
    const draftResult = await generateDraft({
      userId: email.userId,
      threadId: email.gmailThreadId,
      communicationStyle: email.communicationStyle || "professional",
      language: email.language || "en",
      client,
    });

    // Create Gmail draft
    const draft = await client.createDraft({
      threadId: email.gmailThreadId,
      subject: `Re: ${email.subject}`,
      body: draftResult.body,
      inReplyTo: email.gmailMessageId,
    });

    if (!draft.id) {
      throw new Error("Failed to create Gmail draft - no draft ID returned");
    }

    // Update workflow state (pending → drafted)
    await handleDraftCreated({
      userId: email.userId,
      threadId: email.gmailThreadId,
      draftId: draft.id,
      client,
      labelMappings,
    });

    console.log(`✓ Draft created for email ${payload.email_id}: draft_id=${draft.id}`);
  }
}
