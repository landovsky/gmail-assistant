# Test Plan - Gmail Assistant v2

## Overview

This document outlines the testing approach for Gmail Assistant v2. The full specification in `artifacts/specification/12-test-coverage.md` defines **118+ test cases** across:

- Classification accuracy
- Draft generation quality
- Email lifecycle transitions
- Background job processing
- Gmail integration
- Agent execution
- API contracts
- End-to-end workflows

## Current Status

### ✅ Completed (workspace-20 initial setup)

**Test Infrastructure:**
- Created `tests/e2e/` directory for end-to-end tests
- Created `tests/helpers/test-fixtures.ts` - Test data creation helpers
- Created `tests/helpers/mock-clients.ts` - Mock Gmail client and job queue
- Created `tests/e2e/email-lifecycle.test.ts` - E2E test skeleton

**Existing Tests:**
- `tests/unit/llm-prompts.test.ts` - LLM prompt building
- `tests/unit/llm-client.test.ts` - LLM client integration
- `tests/jobs/queue.test.ts` - Job queue operations
- `tests/api/*.test.ts` - API endpoint tests
- `tests/services/gmail/auth.test.ts` - Gmail OAuth

### 🚧 Remaining Work

**Priority 1 - Critical Path (E2E):**
1. Complete email lifecycle E2E test
   - Classification → Draft → Sent flow
   - User marks Done flow
   - Rework flow with limit enforcement

2. Background job processing tests
   - Job queue FIFO ordering
   - Job retry on failure
   - Job permanent failure after max attempts

3. Draft generation E2E tests
   - Initial draft creation
   - Draft matches communication style
   - Draft language matches email

**Priority 2 - Integration Tests:**
1. Gmail integration tests (with mocked API)
   - OAuth flow
   - Token refresh
   - Label provisioning
   - History API sync

2. Classification integration tests
   - Automation detection
   - Newsletter classification
   - Direct question detection
   - Language and style detection

3. Workflow integration tests
   - Sync coordinator
   - Email lifecycle state machine
   - Label management

**Priority 3 - Agent System Tests:**
1. Agent routing tests
2. Agent tool use tests
3. Agent auto-send/escalate flows
4. Preprocessor extraction tests

**Priority 4 - Performance Tests:**
1. Concurrent job processing
2. API retry logic
3. History API pagination

## Testing Approach

### Unit Tests

- **Framework**: Bun's built-in test runner (`bun:test`)
- **Location**: `tests/unit/`
- **Strategy**: Fast, isolated tests with mocks
- **Run**: `bun test tests/unit/`

### Integration Tests

- **Framework**: Bun test with real database
- **Location**: `tests/integration/`
- **Strategy**: Test component interactions with mocked external services
- **Database**: In-memory SQLite for speed
- **Run**: `bun test tests/integration/`

### E2E Tests

- **Framework**: Bun test with full stack
- **Location**: `tests/e2e/`
- **Strategy**: Test complete workflows with mocked Gmail/LLM APIs
- **Fixtures**: Use test helpers in `tests/helpers/`
- **Run**: `bun test tests/e2e/`

### Manual/Live Tests

For tests requiring real Gmail API:
- Use separate test Gmail account
- Manual trigger via CLI: `bun run cli sync --test-mode`
- Monitor via debug UI: `/debug/emails`

## Test Utilities

### Mock Clients

**MockGmailClient** (`tests/helpers/mock-clients.ts`):
- In-memory message/draft/label storage
- Simulates Gmail API operations
- No external dependencies

**MockJobQueue** (`tests/helpers/mock-clients.ts`):
- Implements full JobQueue interface
- FIFO queue with retry logic
- Test helper methods

### Test Fixtures

**createTestUser()** - Creates user with full label setup
**createTestEmail()** - Creates email record
**createMockGmailMessage()** - Builds Gmail API message structure
**cleanTestDatabase()** - Resets database for clean state

## Writing Tests

### Example E2E Test Structure

```typescript
import { describe, it, beforeEach } from 'bun:test';
import { expect } from 'bun:test';
import { createTestUser, createMockGmailMessage, cleanTestDatabase } from '../helpers/test-fixtures.js';
import { MockGmailClient, MockJobQueue } from '../helpers/mock-clients.js';

describe('E2E: Email Classification Flow', () => {
  beforeEach(async () => {
    await cleanTestDatabase();
  });

  it('should classify needs_response and enqueue draft job', async () => {
    // 1. Setup
    const user = await createTestUser();
    const client = new MockGmailClient();
    const queue = new MockJobQueue();

    const message = createMockGmailMessage({
      messageId: 'msg-123',
      threadId: 'thread-123',
      from: 'sender@example.com',
      subject: 'Can you help?',
      body: 'Can you send me the report by Friday?',
    });

    client.addMessage(message);

    // 2. Execute
    const handler = new ClassifyHandler(queue);
    await handler.handle({
      id: 1,
      jobType: 'classify',
      userId: user.id,
      payload: {
        user_id: user.id,
        thread_id: 'thread-123',
        message_id: 'msg-123',
      },
      // ... other job fields
    });

    // 3. Assert
    const draftJobs = queue.getPendingJobs().filter(j => j.jobType === 'draft');
    expect(draftJobs).toHaveLength(1);

    const email = await db.query.emails.findFirst({
      where: eq(emails.gmailThreadId, 'thread-123'),
    });
    expect(email?.classification).toBe('needs_response');
    expect(email?.status).toBe('pending');
  });
});
```

### Test Data Guidelines

- **Use deterministic data** - Same inputs = same outputs
- **Mock LLM responses** - Don't call real APIs in tests
- **Clean state** - Reset database before each test
- **Realistic scenarios** - Use real-world email patterns

## Coverage Goals

Target coverage by area:
- **Email Lifecycle**: 100% (critical path)
- **Job Handlers**: 100% (classify, draft, rework, cleanup)
- **Workflows**: 90% (sync-coordinator, email-lifecycle)
- **Gmail Integration**: 80% (auth, client, sync)
- **LLM Services**: 80% (classification, drafting)
- **API Endpoints**: 90% (REST API, webhooks)
- **Agent System**: 70% (nice to have)

## Running Tests

```bash
# All tests
bun test

# Watch mode
bun test --watch

# Specific suite
bun test tests/e2e/email-lifecycle.test.ts

# With coverage
bun test --coverage
```

## Next Steps

1. Implement critical path E2E tests (email lifecycle)
2. Add integration tests for workflows
3. Expand classification test coverage
4. Add Gmail integration tests
5. Build agent system tests
6. Add performance tests
7. Achieve 80%+ coverage

## References

- Full test specification: `artifacts/specification/12-test-coverage.md`
- Bun test docs: https://bun.sh/docs/cli/test
- Test markers: `@unit`, `@integration`, `@e2e`, `@smoke`
