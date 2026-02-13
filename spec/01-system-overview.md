# 01 — System Overview

## Purpose

Gmail Assistant is a self-hosted service that automatically processes incoming Gmail messages for a user. It classifies each email into one of five categories, generates draft replies for emails that need a response, and manages the entire workflow through Gmail labels. The user interacts primarily through their existing Gmail client — the system applies labels, creates drafts, and responds to label changes the user makes.

## Core Capabilities

1. **Email classification** — Every incoming email is categorized as one of: `needs_response`, `action_required`, `payment_request`, `fyi`, or `waiting`. Classification uses a two-tier approach: deterministic rules (pattern matching, header inspection) followed by LLM-based classification for ambiguous cases.

2. **Draft generation** — Emails classified as `needs_response` automatically get an AI-generated draft reply placed into the Gmail thread. Drafts follow configurable per-contact communication styles and language matching.

3. **Rework loop** — The user can request changes to a generated draft by writing instructions above a marker character (`✂️`) in the draft body and applying a "Rework" label. The system regenerates the draft incorporating the feedback, up to 3 times.

4. **Lifecycle management** — The system monitors Gmail for user actions (marking Done, sending drafts, applying Rework) and updates internal state accordingly. Sent detection works by checking if a draft has disappeared from Gmail.

5. **Agent framework** — A config-driven routing system can direct certain emails (matched by sender, domain, subject, or headers) to an LLM agent loop instead of the standard classify→draft pipeline. Agents have access to registered tools and execute multi-turn conversations.

6. **Context gathering** — Before generating drafts, the system searches the user's mailbox for related prior correspondence and includes it as context for the LLM.

## Architectural Patterns

- **Queue-driven processing**: All work happens through a persistent job queue. Gmail webhooks and polling create sync jobs, which produce classify/draft/agent jobs, which produce cleanup jobs. Workers process jobs concurrently.

- **Label-as-state**: Gmail labels represent the current state of each email in the workflow. The system both reads and writes labels to communicate state changes with the user's Gmail client.

- **User-scoped data**: All database tables include a `user_id` foreign key. The schema supports multiple users, though the current auth model is single-user personal OAuth.

- **LLM-agnostic gateway**: All LLM calls go through a single gateway abstraction that supports any model provider. The system uses a fast/cheap model for classification and a higher-quality model for drafting.

- **Fail-safe defaults**: On LLM parse errors or API failures, classification defaults to `needs_response` (safer to over-triage than miss an email). Context gathering failures are swallowed silently. Draft failures produce an error marker rather than crashing.

## High-Level Data Flow

```
Gmail Inbox
    │
    ▼
Google Pub/Sub push notification ──► Webhook endpoint
    │                                      │
    │                      ┌───────────────┘
    │                      ▼
    │               Enqueue "sync" job
    │                      │
    ▼                      ▼
Fallback polling ──► Sync Engine (History API)
                           │
                    For each new message:
                           │
                    ┌──────┴──────┐
                    ▼             ▼
             Router decides    Router decides
             "pipeline"        "agent"
                    │             │
                    ▼             ▼
            Classify job    Agent process job
                    │             │
              ┌─────┴─────┐      ▼
              ▼           ▼   Agent loop
         Apply label   Queue    (LLM + tools)
                      draft job
                         │
                         ▼
                   Generate draft
                   Create Gmail draft
                   Move label: NR → Outbox
                         │
                         ▼
                   User reviews in Gmail
                    ┌────┼────┐
                    ▼    ▼    ▼
                  Send  Rework Done
                    │    │     │
                    ▼    ▼     ▼
                Detect  Regen  Archive
                sent    draft  thread
```

## System Boundaries

- **Input**: Gmail API (messages, threads, labels, drafts, history)
- **Output**: Gmail API (labels, drafts), local database (state, audit)
- **External LLM**: Any OpenAI-compatible API via model-agnostic gateway
- **Google Pub/Sub**: Receives push notifications for near-real-time processing
- **No user-facing UI**: The user's Gmail client IS the UI. An admin dashboard exists for debugging/monitoring only.

## Multi-Language Support

The system handles emails in Czech, English, and German. Classification prompts are multilingual. Draft generation matches the language of the incoming email by default, unless overridden by style configuration.
