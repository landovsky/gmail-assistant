# 04 — Email Processing Pipeline

## Overview

The email processing pipeline is the core domain logic. It classifies incoming emails, generates draft replies, and manages the lifecycle of each email through label-based state transitions. This document covers classification, draft generation, context gathering, the rework loop, and lifecycle management.

---

## Classification

### Two-Tier Architecture

Classification uses two tiers evaluated in sequence:

1. **Rule-based tier** — Deterministic detection of automated/machine-generated emails via sender patterns and RFC headers. Instant, no external calls. Always runs.
2. **LLM-based tier** — Sends email content to a language model for classification and style detection. Always runs.

The rule tier's sole function is **automation detection** — it identifies machine-generated emails. This detection acts as a safety net: if the LLM classifies an automated email as `needs_response`, the rule engine overrides it to `fyi`.

### Classification Categories

| Category | Meaning | Triggers Draft? |
|----------|---------|----------------|
| `needs_response` | Direct question, personal request, social obligation to reply | Yes |
| `action_required` | Meeting request, signature needed, approval, deadline task | No |
| `payment_request` | Invoice, billing, amount due (unpaid only — payment confirmations classify as `fyi`) | No |
| `fyi` | Newsletter, automated notification, CC'd thread, no action needed | No |
| `waiting` | User sent the last message, awaiting reply | No |

### Rule-Based Detection

The rule tier performs only automation detection — no content-based pattern matching. All classification of email intent (payment, action, response, FYI) is delegated entirely to the LLM.

**Blacklist check:** Sender email matched against glob patterns (e.g., `*@marketing.example.com`). Match → `fyi` with high confidence.

**Automated sender detection:** Sender email contains patterns like `noreply`, `no-reply`, `mailer-daemon`, `postmaster`, `notifications`, `bounce`. Match → `fyi` with high confidence.

**Header-based automation detection:** Checks for RFC 3834 and common automation headers:
- `Auto-Submitted` (value != "no")
- `Precedence` (value in: `bulk`, `list`, `auto_reply`, `junk`)
- `List-Id` (any value)
- `List-Unsubscribe` (any value)
- `X-Auto-Response-Suppress` (any value)
- `Feedback-ID` (any value)
- `X-Autoreply` (any value)
- `X-Autorespond` (any value)

**Rule tier output:** The rule tier returns an `is_automated` flag. This flag is used as a safety net after LLM classification. The rule tier does NOT perform any content-based pattern matching — all classification of email intent (payment, action, response, FYI) is delegated entirely to the LLM.

### LLM Classification

**Input to LLM:**
```
From: {sender_name} <{sender_email}>
Subject: {subject}
Messages in thread: {message_count}

{body, truncated to 2000 characters, or snippet if no body}
```

**System prompt instructs the LLM to:**
- Classify into exactly ONE category
- Follow priority rules (meetings → action_required; invoices → payment_request; direct questions → needs_response; uncertain → prefer needs_response over fyi)
- Detect the appropriate response style for drafting
- Return JSON: `{"category": "...", "confidence": "high|medium|low", "reasoning": "...", "detected_language": "cs|en|de|...", "resolved_style": "..."}`

The LLM classification response includes a `resolved_style` field. The system prompt lists available style names (from `communication_styles` config) and instructs the LLM to select the most appropriate one based on the email's tone, sender relationship signals, and content. Style resolution follows the priority described in "Communication Style Resolution" below.

**Fallback behavior:**
- JSON parse error → defaults to `needs_response` with low confidence (safer to over-triage)
- Unknown category in response → defaults to `needs_response`
- LLM API error → defaults to `needs_response` with low confidence
- Missing `resolved_style` in LLM response → defaults to `business`

### Safety Net

After LLM classification, if the rule engine detected automation signals AND the LLM returned `needs_response`, the classification is overridden to `fyi`. This prevents drafting replies to automated emails.

### Communication Style Resolution

Style is determined by a layered approach:

1. **Exact email match:** Check `contacts.style_overrides` for the sender's exact email → use that style
2. **Domain pattern match:** Check `contacts.domain_overrides` with glob matching on the sender's domain → use that style
3. **LLM-determined:** Use the `resolved_style` returned by the LLM classification response
4. **Fallback:** `business`

---

## Draft Generation

### When Drafts Are Created

A draft job is enqueued when an email is classified as `needs_response`. The draft handler:

1. Verifies the email record exists and has status `pending`
2. Fetches the full Gmail thread (all messages)
3. Gathers related context from the mailbox (optional, fail-safe)
4. Calls the LLM to generate a draft
5. Trashes any stale drafts from previous attempts on this thread
6. Creates a new Gmail draft in the thread
7. Moves labels: removes `Needs Response`, adds `Outbox`
8. Updates database: sets `status=drafted`, stores `draft_id`

### Draft LLM Prompt Structure

**System prompt** (built dynamically from communication style config):
```
You are an email draft generator. Write a reply following the communication style rules below.

Style: {resolved_style}
Language: {language} (if "auto", match the language of the incoming email)

Rules:
- {rule 1}
- {rule 2}
...

Sign-off: {sign_off}

Examples:
Context: {example context}
Input: {example input}
Draft: {example draft}

Guidelines:
- Match the language of the incoming email unless the style specifies otherwise
- Keep drafts concise — match the length and energy of the sender
- Include specific details from the original email
- Never fabricate information. Flag missing context with [TODO: ...]
- Use the sign_off from the style config
- Do NOT include the subject line in the body
- Output ONLY the draft text, nothing else
```

**User message:**
```
From: {sender_name} <{sender_email}>
Subject: {subject}

Thread:
{thread_body, truncated to 3000 characters}

{related context block, if available}

{user instructions block, if manual draft}
```

### Rework Marker

Every generated draft is wrapped with a rework marker:

```
\n\n✂️\n\n{draft text}
```

The marker (`✂️`) separates user instructions (written above) from the AI-generated content (below). When the user wants to request a rework, they type their instructions above the `✂️` in the draft body, then apply the "Rework" label.

### Draft Error Handling

If the LLM call fails, the draft body is set to `[ERROR: Draft generation failed — {error message}]`. The job still completes (the error is visible in the draft).

---

## Context Gathering

Before generating a draft, the system optionally searches the user's mailbox for related prior correspondence.

### Process

Context gathering uses a two-phase approach: first a metadata search to find candidate threads, then full thread fetches to retrieve message bodies. Each thread's combined body is truncated to 2000 characters to prevent prompt bloat.

1. **Generate search queries:** Send the email's sender, subject, and body to the LLM (using the configurable context model — defaults to the fast/cheap model, overridable via `llm.context_model`), which returns up to 3 Gmail search queries as a JSON array.
2. **Execute searches:** Run each query against Gmail's search API to find matching threads.
3. **Deduplicate:** Remove results from the current thread, deduplicate by thread_id.
4. **Cap results:** Maximum 5 related threads.
5. **Fetch full content:** For each related thread, fetch the full thread with all messages. Extract sender, subject, and message bodies (truncated per thread to prevent excessive prompt size).

### Output Format

Related context is formatted as a text block injected into the draft prompt:

```
--- Related emails from your mailbox ---
1. From: Name <email> | Subject: Subject line
   {message body, truncated}
2. From: ...
--- End related emails ---
```

### Failure Handling

Context gathering is entirely fail-safe. Any exception is caught, logged as a warning, and the draft proceeds without context. This includes LLM errors, search API errors, and JSON parse errors.

---

## Rework Loop

### Trigger

The user applies the "Rework" label to a thread in Gmail. The sync engine detects this label change and enqueues a `rework` job.

### Process

The rework process follows the same flow as initial draft generation — it gathers related context, includes it in the prompt, and generates a fresh draft. The only difference is that the prompt additionally includes the user's rework instructions extracted from above the `✂️` marker.

1. Look up the email record and current rework count
2. **Check rework limit (3):**
   - If `rework_count >= 3`: move labels from Rework → Action Required, set status to `skipped`, log `rework_limit_reached` event. Stop.
3. Fetch the current draft from Gmail
4. Extract instruction text (above the `✂️` marker)
5. If no instruction found: use `"(no specific instruction provided)"`
6. Fetch the full Gmail thread (all messages)
7. **Gather related context from the mailbox** (same as initial draft — fail-safe)
8. Call LLM with the standard draft prompt (same system prompt, same thread body, same related context), with the user's rework instructions appended as a user instructions block
9. If this is the 3rd rework (count will become 3): prepend a warning to the draft
10. Trash the old draft
11. Create a new Gmail draft
12. Move labels: Rework → Outbox (or Rework → Action Required if 3rd rework)
13. Update database: increment rework_count, store new draft_id and instruction

### Rework Prompt

The rework prompt is identical to the initial draft prompt (same system prompt built from communication style config), with one addition — the user's rework instruction is included as a user instructions block:

```
From: {sender_name} <{sender_email}>
Subject: {subject}

Thread:
{thread_body, truncated to 3000 characters}

{related context block, if available}

--- User instructions ---
{rework instruction extracted from above ✂️ marker}
--- End instructions ---

Incorporate these instructions into the draft. They guide WHAT to say,
not HOW to say it. The draft should still follow the style rules.
```

### Last Rework Warning

On the 3rd rework, the draft is prefixed with:
```
⚠️ This is the last automatic rework. Further changes must be made manually.
```

---

## Manual Draft

Users can manually request a draft for any email by applying the "Needs Response" label in Gmail. This creates a `manual_draft` job.

The manual draft process is identical to the automatic draft flow — full context gathering, same prompt structure, same LLM call. The only difference is that user instructions (if found in a notes draft) are appended to the prompt.

The manual draft handler:

1. Checks if the email is already drafted (skips if so)
2. Fetches the full Gmail thread (all messages)
3. Looks for a user-written notes draft in the thread (extracts instructions from above the `✂️` marker, or treats the entire draft body as instructions)
4. Creates or updates the database record with `classification=needs_response`
5. **Gathers related context from the mailbox** (same as automatic draft — fail-safe)
6. Generates a draft using the standard draft prompt (same system prompt, same thread body, same related context), with user instructions appended if found
7. Trashes the user's notes draft and any stale AI drafts
8. Creates a new Gmail draft, moves labels (Needs Response → Outbox)

---

## Lifecycle Management

### Done Handler

Triggered when user applies the "Done" label.

1. Get all AI label IDs for the user
2. Fetch all messages in the thread
3. Remove all AI labels (`needs_response`, `outbox`, `rework`, `action_required`, `payment_request`, `fyi`, `waiting`) AND `INBOX` from all messages
4. Keep the "Done" label
5. Update status to `archived`, set `acted_at`
6. Log `archived` event

### Sent Detection

Triggered when Gmail reports a message deletion (which can indicate a draft was sent).

1. Look up the email record and its `draft_id`
2. Check if the draft still exists in Gmail via API
3. If draft is gone: it was likely sent
4. Remove "Outbox" label from all thread messages
5. Update status to `sent`, set `acted_at`
6. Log `sent_detected` event

### Waiting Retriage

Triggered when a new message arrives on a thread labeled "Waiting".

1. Look up stored `message_count` for the thread
2. Fetch current thread and compare message count
3. If new messages arrived: remove "Waiting" label for reclassification
4. Log `waiting_retriaged` event

---

## Label Flow Summary

```
New email arrives
    │
    ▼
Classify → Apply classification label (NR/AR/PR/FYI/W)
    │
    ├── needs_response
    │       │
    │       ▼
    │   Draft → Remove NR, Add Outbox
    │       │
    │       ├── User sends → Detect sent → Remove Outbox
    │       ├── User marks Rework → Remove Outbox(?), Add Rework
    │       │       │
    │       │       ▼
    │       │   Rework → Remove Rework, Add Outbox (or Action Required)
    │       └── User marks Done → Remove all AI labels, Remove INBOX
    │
    ├── action_required → (no draft, user handles manually)
    ├── payment_request → (no draft, user handles manually)
    ├── fyi → (no draft, informational)
    └── waiting → (no draft, monitor for new replies)
```
