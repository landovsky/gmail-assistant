import type { JobHandler } from '../types.js';
import type { Job, AgentProcessPayload } from '../types.js';
import { getAuthenticatedClient } from '../../services/gmail/auth.js';
import { GmailClient } from '../../services/gmail/client.js';
import { AgentExecutor } from '../../agents/executor.js';
import { ProfileLoader, createDefaultProfileConfig } from '../../agents/profiles.js';
import { messageParser } from '../../services/gmail/message-parser.js';

export class AgentProcessHandler implements JobHandler {
  async handle(job: Job): Promise<void> {
    const payload = job.payload as AgentProcessPayload;

    // Get authenticated Gmail client
    const oauth2Client = await getAuthenticatedClient(
      process.env.MASTER_KEY_PATH || 'config/master.key',
      process.env.TOKEN_PATH || 'config/token.json'
    );
    const client = new GmailClient(oauth2Client);

    // Fetch and validate message
    const gmailMessage = await client.getMessage(payload.message_id);
    if (!gmailMessage) {
      throw new Error(`Message ${payload.message_id} not found`);
    }

    // Parse message content
    const parsed = messageParser.parseMessage(gmailMessage);

    // Load agent profile
    const profileLoader = new ProfileLoader(createDefaultProfileConfig());
    const profile = profileLoader.getProfile(payload.profile);

    if (!profile) {
      throw new Error(
        `Agent profile "${payload.profile}" not found. Available profiles: ${profileLoader.getProfileNames().join(', ')}`
      );
    }

    // Load system prompt for this profile
    let systemPrompt: string;
    try {
      systemPrompt = profileLoader.loadSystemPrompt(profile);
    } catch {
      // Fallback: use a basic system prompt if the file is missing
      systemPrompt = `You are an AI assistant processing emails for the "${profile.name}" profile. Respond helpfully and professionally.`;
      console.warn(
        `Warning: Could not load system prompt for profile "${profile.name}", using fallback`
      );
    }

    // Build user message from email content
    const userMessage = buildUserMessage(parsed, payload.thread_id);

    // Execute agent loop
    const executor = new AgentExecutor(profile, payload.user_id, payload.thread_id);

    const result = await executor.execute(systemPrompt, userMessage);

    // Log result based on status
    if (result.status === 'completed') {
      console.log(
        `[ok] Agent "${payload.profile}" completed for thread ${payload.thread_id}: ` +
          `iterations=${result.iterations}, tool_calls=${result.toolCallsLog.length}`
      );
    } else if (result.status === 'max_iterations') {
      console.warn(
        `[warn] Agent "${payload.profile}" hit max iterations for thread ${payload.thread_id}: ` +
          `iterations=${result.iterations}`
      );
    } else if (result.status === 'error') {
      throw new Error(
        `Agent "${payload.profile}" failed for thread ${payload.thread_id}: ${result.error}`
      );
    }
  }
}

/**
 * Build user message from parsed email for agent processing
 */
function buildUserMessage(
  parsed: {
    subject: string;
    from: string;
    to: string;
    date: Date;
    body: string;
    headers: Record<string, string>;
  },
  threadId: string
): string {
  return [
    `Thread ID: ${threadId}`,
    `From: ${parsed.from}`,
    `To: ${parsed.to}`,
    `Date: ${parsed.date.toISOString()}`,
    `Subject: ${parsed.subject}`,
    '',
    '--- Email Body ---',
    parsed.body,
  ].join('\n');
}
