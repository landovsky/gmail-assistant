# Gmail Assistant v2 - System Overview

## Purpose

An AI-powered Gmail inbox management system that automatically classifies incoming emails, generates draft responses, and manages email workflows through Gmail labels. The system acts as an intelligent assistant that helps users prioritize and respond to emails efficiently.

## Core Capabilities

1. **Email Classification**: Automatically categorizes emails into five types:
   - Needs Response - Requires a drafted reply
   - Action Required - User action needed (no draft)
   - Payment Request - Invoice/bill detection
   - FYI - Informational only
   - Waiting - Awaiting external response

2. **Draft Generation**: Creates AI-powered draft responses for emails requiring replies, with support for multiple communication styles and languages

3. **Workflow Management**: Uses Gmail labels to surface email state and guide user actions

4. **Agent Framework**: Supports custom agent profiles that can autonomously handle specific email types using tools

5. **Incremental Sync**: Efficiently tracks Gmail changes via History API with push notification support

## Architecture Style

- **Event-driven**: Gmail changes trigger async job processing
- **User-scoped**: Multi-tenant ready with per-user isolation
- **Async processing**: All heavy work (classification, drafting, sync) runs in background workers
- **Audit-logged**: Every state transition and LLM call is logged for debugging and cost tracking

## System Boundaries

**What the system does:**
- Monitors Gmail inbox for new messages
- Classifies emails into categories
- Creates draft replies (never sends automatically, except for specific agent profiles)
- Manages email state via Gmail labels
- Provides REST API for administration and debugging

**What the system does NOT do:**
- Automatically send emails (only creates drafts for review, except agent routes)
- Delete emails (only archives via labels)
- Modify email content (only labels and drafts)
- Provide a user-facing web UI for reading emails (users interact via Gmail)

## Integration Points

- **Gmail API**: Direct integration for reading, labeling, drafting
- **Gmail Pub/Sub**: Real-time push notifications for inbox changes
- **LLM Providers**: Model-agnostic via LiteLLM gateway (Claude, GPT, Gemini, etc.)
- **Database**: SQLite (default) or PostgreSQL for state management

## Related Documents

- [01-data-model.md](01-data-model.md) - Database schema and relationships
- [02-rest-api.md](02-rest-api.md) - HTTP endpoints and contracts
- [03-gmail-integration.md](03-gmail-integration.md) - Gmail API usage patterns
- [04-background-jobs.md](04-background-jobs.md) - Async job processing
- [05-cli-tools.md](05-cli-tools.md) - Operational commands
- [06-classification.md](06-classification.md) - Two-tier classification logic
- [07-draft-generation.md](07-draft-generation.md) - Draft creation and rework
- [08-email-lifecycle.md](08-email-lifecycle.md) - State machine and transitions
- [09-agent-system.md](09-agent-system.md) - Agent framework and routing
- [10-auth-config.md](10-auth-config.md) - Authentication and configuration
- [11-llm-integration.md](11-llm-integration.md) - LLM gateway patterns
- [12-test-coverage.md](12-test-coverage.md) - Integration test cases
- [13-ui-interfaces.md](13-ui-interfaces.md) - Browser-based UI specifications
