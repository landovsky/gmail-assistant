# Draft Generation

## Purpose

Automatically generates high-quality email draft responses for emails classified as "needs_response", using LLM to match the sender's communication style and language.

## Initial Draft Generation

### Inputs

**Email Context**:
- Email thread (sender, subject, body, all messages in conversation)
- Classification metadata (category, confidence, reasoning)
- Detected language
- Resolved communication style

**Related Context** (gathered via Context Gathering System):
- Related email threads from mailbox (up to 3)
- Found via LLM-generated Gmail search queries
- Provides background information for informed responses

**User Configuration**:
- Sign-off name
- Communication style templates
- Language preferences

**Optional**:
- User instructions (for manual draft requests)

### Context Gathering System

**Purpose**: Find related email threads to inform draft responses

**Process**:
1. Call LLM with email content
2. LLM generates up to 3 Gmail search queries
3. Execute queries against Gmail API
4. Deduplicate and limit to 3 threads
5. Format as context block for draft prompt

**Example Context Block**:
```
Related context from your mailbox:
- [Thread: "Previous discussion about project timeline"]
  Snippet of relevant conversation...

- [Thread: "Budget approval for Q1"]
  Snippet of relevant conversation...
```

### Draft Generation Process

1. **Trash stale drafts**: Remove any existing drafts for this thread
2. **Gather context**: Run context gathering system
3. **Build prompt**:
   - System prompt: Role definition, style guidelines, language instructions
   - User message: Email thread, related context, communication style, user instructions
4. **Call LLM**:
   - Model: High-quality (default: Gemini 2.5 Pro)
   - Temperature: 0.3 (creative but consistent)
   - Max tokens: 2048
5. **Add rework marker**: Append scissors emoji (✂️) as separator for rework instructions
6. **Create Gmail draft**:
   - MIME-encoded reply
   - Proper threading headers (In-Reply-To, References)
   - Base64 encoded body
7. **Store draft ID**: Save Gmail draft ID in email record
8. **Update status**: Set email status to "drafted"
9. **Apply label**: Add "Outbox" label to thread
10. **Log events**: drafted event, LLM call

### Draft Format

```
[Draft response text in sender's language and style]

---
✂️
[Space for user rework instructions]
```

The scissors emoji (✂️) acts as:
- Separator between draft and rework instructions
- Marker to identify AI-generated drafts
- Cut point for extracting user feedback

### Communication Styles

**Formal**:
- Very polite, structured language
- Traditional business formalities
- Complete sentences, proper grammar
- Respectful distance

**Business** (default):
- Professional but approachable
- Clear and concise
- Balances formality with friendliness
- Modern business communication

**Informal**:
- Casual, friendly tone
- Relaxed grammar
- Conversational style
- Personal connection

Style templates include:
- Greeting patterns
- Sign-off patterns
- Tone guidelines
- Example messages

### LLM Model
- High-quality model (default: Gemini 2.5 Pro)
- Temperature: 0.3 (balance creativity and consistency)
- Token limit: 2048 (allows for detailed responses)

## Rework Loop

### Purpose
Allow users to provide feedback and refine drafts without starting from scratch.

### Trigger
User adds rework instructions above the ✂️ marker in the draft, then applies the "Rework" label.

### Rework Process

1. **Fetch existing draft**: Get draft content from Gmail
2. **Extract instruction**: Parse text above ✂️ marker
3. **Check rework limit**: Verify rework_count < 3
4. **Gather context**: Re-run context gathering (may find new threads)
5. **Build rework prompt**:
   - System prompt: Same as initial draft
   - User message: Original thread + Old draft + User feedback + Related context
6. **Call LLM**:
   - Same model and settings as initial draft
   - Incorporates user feedback
7. **Trash old draft**: Remove previous draft from Gmail
8. **Create new draft**: With rework marker
9. **Update counters**: Increment rework_count
10. **Update status**: Keep as "drafted"
11. **Update label**: Keep "Outbox" label (or move to "Action Required" if limit reached)
12. **Log events**: draft_reworked event, LLM call

### Rework Limit Enforcement

**Hard Limit**: 3 rework iterations per thread

**On 4th Rework Attempt**:
1. **Warning**: Add warning message to draft about reaching limit
2. **Status**: Change status to "skipped"
3. **Label**: Move from "Outbox" to "Action Required"
4. **Event**: Log rework_limit_reached
5. **Reasoning**: Prevent infinite LLM loops, escalate to human

**User Options After Limit**:
- Send current draft
- Mark as Done (archive)
- Handle manually in Gmail

### Rework Instruction Examples

User writes above ✂️:
```
Make this shorter and more direct.
```

Or:
```
Add mention of the budget constraints we discussed last week.
```

Or:
```
Be more formal, this is going to the CEO.
```

### Rework vs. Manual Edit

**Rework** (via LLM):
- User provides high-level instructions
- LLM regenerates entire draft
- Preserves context and style
- Use for: significant changes, tone adjustments, adding/removing topics

**Manual Edit** (direct editing):
- User edits draft text directly in Gmail
- No LLM involved
- Use for: typos, small tweaks, final polish before sending

## Manual Draft Request

### Trigger
User manually applies "Needs Response" label to any email.

### Behavior
- If email not in database: Create email record with placeholder classification
- If email already drafted: Skip (no duplicate draft)
- Otherwise: Same process as automatic draft generation
- Useful for: Emails that were initially classified as "fyi" or "action_required" but user wants draft

## Draft Lifecycle

```
Classification: needs_response
    ↓
Enqueue draft job
    ↓
Generate initial draft
    ↓
Status: drafted, Label: Outbox
    ↓
User reviews in Gmail
    ↓
Decision:
├─ Send draft → Draft deleted → Sent detection → Status: sent
├─ Apply Rework label → Rework job → New draft (rework_count++)
├─ Apply Done label → Cleanup → Status: archived
└─ Edit manually → User handles in Gmail
```

## Draft Quality Guidelines

The LLM is instructed to:

**Content**:
- Directly address sender's questions/requests
- Be helpful and informative
- Include relevant details from context
- Avoid making promises without data

**Tone**:
- Match sender's communication style
- Be professional yet personable
- Adapt formality to relationship

**Structure**:
- Clear greeting
- Direct response to main points
- Logical flow
- Appropriate sign-off

**Language**:
- Use sender's language (Czech/English/etc.)
- Grammar and spelling accuracy
- Natural phrasing
- Culturally appropriate

**Length**:
- Concise but complete
- No unnecessary verbosity
- Proportional to sender's email

## Context Quality

The draft system benefits from related context:

**Good Context** (improves draft):
- Previous conversations with same sender
- Related project discussions
- Relevant background information
- Prior commitments or decisions

**Poor Context** (ignored or filtered):
- Unrelated threads
- Very old conversations
- Duplicate information
- Noise from automated emails

Context gathering uses LLM to generate smart queries that find truly relevant threads.

## Error Handling

### Draft Creation Failures
- Log error with details
- Retry job (up to 3 attempts)
- If permanent failure: Log to email_events as error
- User sees email remains in classification label (no Outbox)

### Gmail API Errors
- Exponential backoff retry (1s, 2s, 4s)
- Handles transient failures
- Permanent failures logged

### LLM Failures
- Retry on timeout/rate limit
- Fallback to simpler prompt if context too large
- Error logged with full details for debugging

## Audit Trail

Every draft generation is logged:
- Email record: draft_id, drafted_at, rework_count
- Event record: draft_created or draft_reworked
- LLM call record: full prompt, response, tokens, latency
- All data available via debug API

## Draft Deletion Detection

When user sends draft:
- Gmail deletes the draft
- System detects deletion via History API (messagesDeleted event)
- Cleanup job verifies draft_id no longer exists
- Status updated to "sent"
- Labels cleaned up
- Completion logged

## Manual Draft Handling

Users can:
- Edit drafts directly in Gmail (no rework job triggered)
- Delete drafts (cleanup job detects and updates status)
- Create their own drafts (system ignores non-AI drafts via ✂️ marker check)
- Move threads to "Done" label (cleanup job archives)

The system is designed to augment, not replace, user control over email.
