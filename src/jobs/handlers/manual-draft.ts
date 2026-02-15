import type { JobHandler } from '../types.js';
import type { Job, ManualDraftPayload } from '../types.js';
import { getAuthenticatedClient } from '../../services/gmail/auth.js';
import { GmailClient } from '../../services/gmail/client.js';
import { generateDraft } from '../../services/drafting/adapter.js';
import { handleDraftCreated } from '../../workflows/index.js';
import { db } from '../../db/index.js';
import { emails, userLabels } from '../../db/schema.js';
import { eq, and } from 'drizzle-orm';
import { messageParser } from '../../services/gmail/message-parser.js';

export class ManualDraftHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as ManualDraftPayload;

    // Get authenticated Gmail client
    const oauth2Client = await getAuthenticatedClient(
      process.env.MASTER_KEY_PATH || 'config/master.key',
      process.env.TOKEN_PATH || 'config/token.json'
    );
    const client = new GmailClient(oauth2Client);

    // Check if email record already exists for this thread
    let email = await db.query.emails.findFirst({
      where: and(eq(emails.userId, payload.user_id), eq(emails.gmailThreadId, payload.thread_id)),
    });

    // Skip if already drafted
    if (email && email.status === 'drafted') {
      console.log(`- Manual draft skipped for thread ${payload.thread_id}: already drafted`);
      return;
    }

    // If no email record exists, create one from Gmail thread data
    if (!email) {
      const thread = await client.getThread(payload.thread_id);
      const lastMessage = thread.messages?.[thread.messages.length - 1];

      if (!lastMessage) {
        throw new Error(`No messages found in thread ${payload.thread_id}`);
      }

      const parsed = messageParser.parseMessage(lastMessage);

      const [newEmail] = await db
        .insert(emails)
        .values({
          userId: payload.user_id,
          gmailThreadId: payload.thread_id,
          gmailMessageId: lastMessage.id || '',
          senderEmail: parsed.from,
          subject: parsed.subject,
          snippet: parsed.body.substring(0, 500),
          classification: 'needs_response',
          status: 'pending',
          detectedLanguage: 'en',
          resolvedStyle: 'business',
          messageCount: thread.messages?.length || 1,
        })
        .returning();

      email = newEmail;
    }

    // Load user's label mappings
    const labels = await db.query.userLabels.findMany({
      where: eq(userLabels.userId, payload.user_id),
    });

    const labelMappings = labels.map((l) => ({
      key: l.labelKey,
      name: l.gmailLabelName,
      gmailLabelId: l.gmailLabelId,
    }));

    // Generate draft (same as draft handler)
    const draftResult = await generateDraft({
      userId: email.userId,
      threadId: email.gmailThreadId,
      subject: email.subject || '',
      from: email.senderEmail,
      body: email.snippet || '',
      communicationStyle: (email.resolvedStyle as 'formal' | 'business' | 'informal') || 'business',
      language: email.detectedLanguage || 'en',
      client,
    });

    // Create Gmail draft
    const draft = await client.createDraft(
      email.gmailThreadId,
      email.senderEmail,
      `Re: ${email.subject || ''}`,
      draftResult.body,
      email.gmailMessageId
    );

    if (!draft.draftId) {
      throw new Error('Failed to create Gmail draft - no draft ID returned');
    }

    // Update workflow state (pending -> drafted)
    await handleDraftCreated({
      userId: email.userId,
      threadId: email.gmailThreadId,
      draftId: draft.draftId,
      client,
      labelMappings,
    });

    console.log(
      `[ok] Manual draft created for thread ${payload.thread_id}: draft_id=${draft.draftId}`
    );
  }
}
