import type { JobHandler } from "../types.js";
import type { Job, SyncPayload } from "../types.js";
import { getAuthenticatedClient } from "../../services/gmail/auth.js";
import { GmailClient } from "../../services/gmail/client.js";
import { performFullSync, performIncrementalSync, handleSentDetected } from "../../workflows/index.js";
import { db } from "../../db/index.js";
import { userLabels } from "../../db/schema.js";
import { eq } from "drizzle-orm";

export class SyncHandler implements JobHandler {
  private queue: any; // JobQueue injected via constructor

  constructor(queue: any) {
    this.queue = queue;
  }

  async handle(job: Job): Promise<void> {
    const payload = job.payload as SyncPayload;

    // Get authenticated Gmail client
    const oauth2Client = await getAuthenticatedClient(
      process.env.MASTER_KEY_PATH || "config/master.key",
      process.env.TOKEN_PATH || "config/token.json"
    );
    const client = new GmailClient(oauth2Client);

    // Load user's label mappings
    const labels = await db.query.userLabels.findMany({
      where: eq(userLabels.userId, payload.user_id),
    });

    const labelMappings = labels.map((l) => ({
      key: l.labelKey,
      name: l.labelName,
      gmailLabelId: l.gmailLabelId,
    }));

    // Handle specific sync actions
    if (payload.action === "detect_sent") {
      // Detect if draft was sent
      await handleSentDetected({
        userId: payload.user_id,
        threadId: payload.thread_id!,
        client,
        labelMappings,
      });
      return;
    }

    // Perform full or incremental sync
    const syncFn = payload.force_full ? performFullSync : performIncrementalSync;

    const result = await syncFn({
      userId: payload.user_id,
      client,
      queue: this.queue,
      labelMappings,
    });

    console.log(
      `✓ Sync complete for user ${payload.user_id}: ${result.messagesProcessed} messages, ${result.draftsCreated} drafts queued, ${result.labelsChanged} labels changed, ${result.errors.length} errors`
    );

    if (result.errors.length > 0) {
      console.error("Sync errors:", result.errors);
    }
  }
}
