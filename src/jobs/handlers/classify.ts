import type { JobHandler } from "../types.js";
import type { Job, ClassifyPayload } from "../types.js";
import { getAuthenticatedClient } from "../../services/gmail/auth.js";
import { GmailClient } from "../../services/gmail/client.js";
import { classify } from "../../services/classification/adapter.js";
import { handleClassificationComplete } from "../../workflows/index.js";
import { db } from "../../db/index.js";
import { emails, userLabels } from "../../db/schema.js";
import { eq } from "drizzle-orm";
import { messageParser } from "../../services/gmail/message-parser.js";

export class ClassifyHandler implements JobHandler {
  private queue: any; // JobQueue injected via constructor

  constructor(queue: any) {
    this.queue = queue;
  }

  async handle(job: Job): Promise<void> {
    const payload = job.payload as ClassifyPayload;

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

    // Fetch message details
    const gmailMessage = await client.getMessage(payload.message_id);

    if (!gmailMessage) {
      throw new Error(`Message ${payload.message_id} not found`);
    }

    // Parse message
    const message = messageParser.parseMessage(gmailMessage);

    // Classify the email
    const classification = await classify({
      userId: payload.user_id,
      threadId: payload.thread_id,
      messageId: payload.message_id,
      subject: message.subject,
      from: message.from,
      body: message.body,
      headers: message.headers,
    }, labelMappings);

    // Create email record
    const [email] = await db
      .insert(emails)
      .values({
        userId: payload.user_id,
        gmailThreadId: payload.thread_id,
        gmailMessageId: payload.message_id,
        subject: message.subject,
        from: message.from,
        classification: classification.category,
        status: classification.category === "needs_response" ? "pending" : "skipped",
        classificationLabel: classification.labelId,
        communicationStyle: classification.communicationStyle,
        language: classification.language,
        messageCount: 1,
      })
      .returning();

    // Handle classification complete (applies labels, logs event)
    await handleClassificationComplete({
      userId: payload.user_id,
      threadId: payload.thread_id,
      classification: classification.category,
      labelId: classification.labelId,
      emailId: email.id,
    });

    // If needs response, enqueue draft job
    if (classification.category === "needs_response") {
      await this.queue.enqueue({
        type: "draft",
        userId: payload.user_id,
        payload: {
          threadId: payload.thread_id,
          emailId: email.id,
        },
      });

      console.log(`✓ Email classified as needs_response - draft job queued: email_id=${email.id}`);
    } else {
      console.log(`✓ Email classified as ${classification.category}: email_id=${email.id}`);
    }
  }
}
