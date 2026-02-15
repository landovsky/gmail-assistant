# Integration Tasks - Workspace-18 Unblocking

## Overview

Shared API contracts defined in `src/shared/types/api.ts`. Each worker needs to create adapter functions that map their existing implementations to these contracts.

## Worker Assignments

### llm-worker: Classification & Drafting Adapters

**File: `src/services/classification/adapter.ts`**

```typescript
import type { IClassificationService, ClassificationInput, ClassificationResult } from '../../shared/types/api.js';
import { classifyEmailTwoTier } from './engine.js';
import type { GmailClient } from '../gmail/client.js';

/**
 * Adapter: Maps shared API contract to classification engine implementation
 */
export async function classify(
  input: ClassificationInput,
  labelMappings: Array<{key: string, gmailLabelId: string}>
): Promise<ClassificationResult> {
  // Call existing classifyEmailTwoTier function
  const result = await classifyEmailTwoTier({
    email: {
      senderEmail: input.from,
      senderName: input.senderName,
      subject: input.subject,
      body: input.body,
    },
    headers: input.headers,
    userId: input.userId,
    threadId: input.threadId,
  });

  // Map category label key to Gmail label ID
  const labelMapping = labelMappings.find(l => l.key === result.finalClassification);

  // Return in shared contract format
  return {
    category: result.finalClassification as any,
    confidence: result.confidence,
    reasoning: result.reasoning,
    language: result.detected_language,
    communicationStyle: result.style as any,
    isAutomated: result.isAutomated,
    automationReason: result.automationReason,
    labelId: labelMapping?.gmailLabelId || '',
  };
}
```

**File: `src/services/drafting/adapter.ts`**

```typescript
import type { IDraftService, DraftGenerationInput, DraftResult } from '../../shared/types/api.js';
import { generateEmailDraft } from './engine.js';
import { handleDraftRework } from './rework.js';
import { GmailClient } from '../gmail/client.js';

/**
 * Adapter: Maps shared API contract to draft generation engine
 */
export async function generateDraft(input: DraftGenerationInput): Promise<DraftResult> {
  // Fetch thread messages
  const thread = await input.client.getThread(input.threadId);
  const messages = (thread.messages || []).map(msg => {
    // Parse message details
    const headers = msg.payload?.headers || [];
    const fromHeader = headers.find(h => h.name?.toLowerCase() === 'from');
    const dateHeader = headers.find(h => h.name?.toLowerCase() === 'date');

    return {
      from: fromHeader?.value || '',
      date: dateHeader?.value || '',
      body: extractPlainTextBody(msg),
    };
  });

  // Create gmailSearch function
  const gmailSearch = async (query: string) => {
    const results = await input.client.listMessages(query);
    return results.map(msg => ({
      threadId: msg.threadId || '',
      subject: extractSubject(msg),
      snippet: msg.snippet || '',
    }));
  };

  // Call existing generateEmailDraft
  const result = await generateEmailDraft({
    threadId: input.threadId,
    subject: input.subject,
    messages,
    senderEmail: input.from,
    style: input.communicationStyle,
    language: input.language,
    signOffName: input.signOffName,
    userInstructions: input.userInstructions,
    gmailSearch,
    userId: input.userId,
  });

  return {
    body: result.draftWithMarker,
    plainBody: result.draftText,
    relatedContext: result.relatedContext,
  };
}

export async function regenerateDraft(
  input: DraftGenerationInput & { draftId: string }
): Promise<DraftResult & { instruction: string }> {
  // Fetch existing draft
  const draft = await input.client.getDraft(input.draftId);
  const draftBody = extractPlainTextBody(draft.message!);

  // Extract instruction from draft
  const parts = draftBody.split('✂️');
  const instruction = parts[0]?.trim() || '';

  // Regenerate draft
  const newDraft = await generateDraft({
    ...input,
    userInstructions: instruction,
  });

  return {
    ...newDraft,
    instruction,
  };
}

// Helper functions (move to shared/utils if needed)
function extractPlainTextBody(message: any): string {
  // Implementation from gmail/client.ts
  if (!message.payload) return '';
  if (message.payload.body?.data) {
    return Buffer.from(message.payload.body.data, 'base64url').toString('utf-8');
  }
  // Handle multipart...
  return '';
}

function extractSubject(message: any): string {
  const headers = message.payload?.headers || [];
  const subjectHeader = headers.find((h: any) => h.name?.toLowerCase() === 'subject');
  return subjectHeader?.value || '';
}
```

**Tasks:**
1. Create `src/services/classification/adapter.ts`
2. Create `src/services/drafting/adapter.ts`
3. Add exports to `src/services/classification/index.ts`:
   ```typescript
   export { classify } from './adapter.js';
   ```
4. Add exports to `src/services/drafting/index.ts`:
   ```typescript
   export { generateDraft, regenerateDraft } from './adapter.js';
   ```
5. Verify TypeScript compiles

---

### gmail-worker: Sync & Message Parsing Adapters

**File: `src/services/gmail/sync-adapter.ts`**

```typescript
import type { ISyncService, SyncResult, SyncMessageDetails, SyncHistoryEvent } from '../../shared/types/api.js';
import { GmailSyncEngine } from './sync.js';
import { GmailClient } from './client.js';

/**
 * Adapter: Maps shared API contract to Gmail sync engine
 */
export async function sync(
  userId: number,
  client: GmailClient,
  lastHistoryId?: string
): Promise<SyncResult> {
  // If no history ID, do full sync (fetch recent messages)
  if (!lastHistoryId) {
    return fullSync(client);
  }

  // Incremental sync using GmailSyncEngine
  const labelMapping = {}; // TODO: Load from database
  const engine = new GmailSyncEngine(client, labelMapping);

  const syncResult = await engine.sync(lastHistoryId);

  // Fetch full details for new messages
  const messageDetails: SyncMessageDetails[] = [];
  for (const threadId of syncResult.newMessages) {
    const thread = await client.getThread(threadId);
    const latestMessage = thread.messages?.[thread.messages.length - 1];

    if (latestMessage) {
      messageDetails.push(parseMessageToDetails(latestMessage));
    }
  }

  // Convert label changes to history events
  const historyEvents: SyncHistoryEvent[] = syncResult.labelChanges.map(change => ({
    type: change.addedLabels.length > 0 ? 'labelsAdded' : 'labelsRemoved',
    threadId: change.threadId,
    messageId: change.messageId,
    labelIds: change.addedLabels.length > 0 ? change.addedLabels : change.removedLabels,
  }));

  // Add deleted messages events
  historyEvents.push(...syncResult.deletedMessages.map(id => ({
    type: 'messagesDeleted' as const,
    threadId: '', // Not available from sync
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
  // Fetch recent INBOX messages
  const messages = await client.listMessages('in:inbox', 50);

  const messageDetails: SyncMessageDetails[] = [];
  for (const msg of messages) {
    const fullMessage = await client.getMessage(msg.id!);
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

function parseMessageToDetails(message: any): SyncMessageDetails {
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

function getHeader(headers: any[], name: string): string {
  const header = headers.find(h => h.name?.toLowerCase() === name.toLowerCase());
  return header?.value || '';
}

function headersToRecord(headers: any[]): Record<string, string> {
  const record: Record<string, string> = {};
  for (const header of headers) {
    if (header.name && header.value) {
      record[header.name] = header.value;
    }
  }
  return record;
}

function extractPlainTextBody(message: any): string {
  // Use existing extractPlainTextBody from client.ts
  // Or inline implementation here
  return '';
}
```

**File: `src/services/gmail/message-parser.ts`**

```typescript
import type { IGmailMessageParser } from '../../shared/types/api.js';
import { gmail_v1 } from 'googleapis';

/**
 * Gmail message parser implementation
 */
export const messageParser: IGmailMessageParser = {
  parseMessage(message: gmail_v1.Schema$Message) {
    const headers = message.payload?.headers || [];

    return {
      subject: getHeader(headers, 'subject'),
      from: getHeader(headers, 'from'),
      to: getHeader(headers, 'to'),
      date: new Date(getHeader(headers, 'date') || Date.now()),
      body: extractPlainTextBody(message),
      headers: headersToRecord(headers),
    };
  },
};

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

function extractPlainTextBody(message: gmail_v1.Schema$Message): string {
  if (!message.payload) return '';

  // Single part message
  if (message.payload.body?.data) {
    return Buffer.from(message.payload.body.data, 'base64url').toString('utf-8');
  }

  // Multipart message - find text/plain part
  if (message.payload.parts) {
    for (const part of message.payload.parts) {
      if (part.mimeType === 'text/plain' && part.body?.data) {
        return Buffer.from(part.body.data, 'base64url').toString('utf-8');
      }
    }
  }

  return '';
}
```

**Tasks:**
1. Create `src/services/gmail/sync-adapter.ts`
2. Create `src/services/gmail/message-parser.ts`
3. Add exports to `src/services/gmail/index.ts`:
   ```typescript
   export { sync } from './sync-adapter.js';
   export { messageParser } from './message-parser.js';
   ```
4. Move `extractPlainTextBody` from client.ts to message-parser.ts and export it
5. Verify TypeScript compiles

---

### team-lead (me): Update Workflow Code

**Tasks:**
1. Update `src/workflows/sync-coordinator.ts` to use `sync()` from adapter
2. Update `src/jobs/handlers/classify.ts` to use `classify()` from adapter
3. Update `src/jobs/handlers/draft.ts` to use `generateDraft()` from adapter
4. Update `src/jobs/handlers/rework.ts` to use `regenerateDraft()` from adapter
5. Add proper type imports from `src/shared/types/api.ts`
6. Remove old function calls
7. Verify TypeScript compiles

---

## Timeline

**Phase 1: Create Adapters (Workers)** - 2-3 hours
- llm-worker: classification + drafting adapters
- gmail-worker: sync + message parsing adapters

**Phase 2: Update Workflow Code (Team Lead)** - 1 hour
- Update all handler imports
- Verify compilation

**Phase 3: Integration Testing** - 1 hour
- Run TypeScript compiler
- Fix any remaining type errors
- Verify build succeeds

**Total: 4-5 hours to unblock workspace-18**

## Success Criteria

- [ ] TypeScript compiles with 0 errors
- [ ] All imports resolve correctly
- [ ] Shared API contracts implemented by all services
- [ ] Workflow handlers use adapter functions
- [ ] workspace-18 ready for merge
