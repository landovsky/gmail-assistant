import type { JobHandler } from "../types.js";
import type { Job, ReworkPayload } from "../types.js";
import { getAuthenticatedClient } from "../../services/gmail/auth.js";
import { GmailClient } from "../../services/gmail/client.js";
import { regenerateDraft } from "../../services/drafting/adapter.js";
import { handleReworkRequested, handleDraftCreated } from "../../workflows/index.js";
import { db } from "../../db/index.js";
import { emails, userLabels } from "../../db/schema.js";
import { eq } from "drizzle-orm";

export class ReworkHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as ReworkPayload;

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

    // Handle rework request (checks limit, increments count)
    const reworkResult = await handleReworkRequested({
      userId: email.userId,
      threadId: email.gmailThreadId,
    });

    if (reworkResult.newStatus === "skipped") {
      // Rework limit reached
      const actionRequiredLabelId = labelMappings.find((l) => l.key === "action_required")?.gmailLabelId;
      const outboxLabelId = labelMappings.find((l) => l.key === "outbox")?.gmailLabelId;

      if (actionRequiredLabelId && outboxLabelId) {
        await client.modifyThreadLabels(email.gmailThreadId, {
          addLabelIds: [actionRequiredLabelId],
          removeLabelIds: [outboxLabelId],
        });
      }

      console.log(`✗ Rework limit reached for email ${payload.email_id} - moved to Action Required`);
      return;
    }

    // Regenerate draft with user feedback
    const reworked = await regenerateDraft({
      userId: email.userId,
      threadId: email.gmailThreadId,
      draftId: email.draftId!,
      communicationStyle: email.communicationStyle || "professional",
      language: email.language || "en",
      client,
    });

    // Create new Gmail draft
    const draft = await client.createDraft({
      threadId: email.gmailThreadId,
      subject: `Re: ${email.subject}`,
      body: reworked.body,
      inReplyTo: email.gmailMessageId,
    });

    if (!draft.id) {
      throw new Error("Failed to create reworked draft - no draft ID returned");
    }

    // Trash old draft
    if (email.draftId) {
      await client.trashDraft(email.draftId);
    }

    // Update draft ID
    await db
      .update(emails)
      .set({
        draftId: draft.id,
        lastReworkInstruction: reworked.instruction,
      })
      .where(eq(emails.id, email.id));

    console.log(`✓ Draft reworked for email ${payload.email_id}: new_draft_id=${draft.id}, instruction="${reworked.instruction}"`);
  }
}
