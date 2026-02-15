// Gmail sync adapter
import type { SyncResult, SyncMessageDetails, SyncHistoryEvent } from '../../shared/types/api.js';
import { GmailSyncEngine } from './sync.js';
import { GmailClient } from './client.js';
import { extractPlainTextBody } from './message-parser.js';
import { gmail_v1 } from 'googleapis';

export async function sync(
  userId: number,
  client: GmailClient,
  lastHistoryId?: string
): Promise<SyncResult> {
  if (!lastHistoryId) {
    return fullSync(client);
  }

  const labelMapping = {};
  const engine = new GmailSyncEngine(client, labelMapping);
  const syncResult = await engine.sync(lastHistoryId);

  const messageDetails: SyncMessageDetails[] = [];
  for (const threadId of syncResult.newMessages) {
    const thread = await client.getThread(threadId);
    const latestMessage = thread.messages?.[thread.messages.length - 1];
    if (latestMessage) {
      messageDetails.push(parseMessageToDetails(latestMessage));
    }
  }

  const historyEvents: SyncHistoryEvent[] = syncResult.labelChanges.map(change => ({
    type: change.addedLabels.length > 0 ? 'labelsAdded' as const : 'labelsRemoved' as const,
    threadId: change.threadId,
    messageId: change.messageId,
    labelIds: change.addedLabels.length > 0 ? change.addedLabels : change.removedLabels,
  }));

  historyEvents.push(...syncResult.deletedMessages.map(id => ({
    type: 'messagesDeleted' as const,
    threadId: '',
    messageIds: [id],
  })));

  return {
    newMessages: messageDetails,
    historyEvents,
    newHistoryId: syncResult.updatedHistoryId,
    processedRecords: syncResult.processedHistoryRecords,
  };
}

async function fullSync(client: GmailClient): Promise<SyncResult> {
  const messages = await client.listMessages('in:inbox', 50);
  const messageDetails: SyncMessageDetails[] = [];

  for (const msg of messages) {
    if (!msg.id) continue;
    const fullMessage = await client.getMessage(msg.id);
    messageDetails.push(parseMessageToDetails(fullMessage));
  }

  const profile = await client.getProfile();

  return {
    newMessages: messageDetails,
    historyEvents: [],
    newHistoryId: profile.historyId,
    processedRecords: messages.length,
  };
}

function parseMessageToDetails(message: gmail_v1.Schema$Message): SyncMessageDetails {
  const headers = message.payload?.headers || [];
  return {
    threadId: message.threadId || '',
    messageId: message.id || '',
    subject: getHeader(headers, 'subject'),
    from: getHeader(headers, 'from'),
    to: getHeader(headers, 'to'),
    body: extractPlainTextBody(message),
    headers: headersToRecord(headers),
    date: new Date(getHeader(headers, 'date') || Date.now()),
    labelIds: message.labelIds || [],
  };
}

function getHeader(headers: gmail_v1.Schema$MessagePartHeader[], name: string): string {
  const header = headers.find(h => h.name?.toLowerCase() === name.toLowerCase());
  return header?.value || '';
}

function headersToRecord(headers: gmail_v1.Schema$MessagePartHeader[]): Record<string, string> {
  const record: Record<string, string> = {};
  for (const header of headers) {
    if (header.name && header.value) {
      record[header.name] = header.value;
    }
  }
  return record;
}
