# Email Classification

## Two-Tier Classification System

The system uses a two-tier approach to classify emails efficiently and accurately:

1. **Tier 1: Rule-Based Automation Detection** - Fast, free, catches obvious patterns
2. **Tier 2: LLM Classification** - Intelligent, context-aware, handles nuanced cases

## Tier 1: Rule-Based Automation Detection

### Purpose
Detects machine-generated emails to prevent unnecessary draft generation and LLM costs.

### Checks Performed

**Blacklist Patterns**:
- Glob-based pattern matching against sender email
- Examples: `noreply@*.com`, `*-noreply@*`, `notifications@github.com`
- Configured per-user in contacts.blacklist

**Automated Sender Patterns**:
Detects common automation sender patterns:
- noreply, no-reply, do-not-reply, donotreply
- mailer-daemon, postmaster
- automated, notification, notifications
- updates, alerts, news

**RFC Headers**:
Checks email headers for automation indicators:
- Auto-Submitted: auto-* (RFC 3834)
- Precedence: bulk | list | junk
- List-Unsubscribe: presence indicates mailing list
- List-Id: presence indicates mailing list
- X-Auto-Response-Suppress: presence indicates automation

### Output
- `is_automated`: Boolean flag
- If true, classification defaults to "fyi" and no draft is generated

### Safety Net
If rules detect automation but LLM classifies as "needs_response", the engine overrides to "fyi".

## Tier 2: LLM Classification

### Purpose
Intelligently categorizes emails based on content, context, and intent.

### Input to LLM
- Sender email and name
- Subject line
- Email body (plain text)
- Thread context (if multi-message thread)

### Classification Categories

**needs_response** - Direct questions, requests requiring reply
- Examples:
  - "Can you send me the report by Friday?"
  - "What's the status of the project?"
  - "Could you help me with X?"
- Triggers: Draft generation job

**action_required** - Meeting requests, tasks, approvals (no draft needed)
- Examples:
  - Calendar invitations
  - Task assignments
  - Approval requests that require clicking a link
- Result: Labeled, no draft created

**payment_request** - Invoices, bills (unpaid only)
- Detection criteria:
  - Contains invoice number or bill reference
  - Shows amount due
  - Payment instructions present
  - NOT already paid/receipt
- Special field: Extracts vendor_name
- Result: Labeled with Payment Requests label

**fyi** - Newsletters, notifications, no action needed
- Examples:
  - Marketing emails
  - System notifications
  - Newsletters
  - Automated reports
- Result: Labeled as FYI, no draft

**waiting** - User sent last message, awaiting reply
- Detection: User's email is the last message in thread
- Purpose: Track conversations where user is waiting for response
- Result: Labeled as Waiting
- Special behavior: New replies trigger automatic reclassification

### Additional Outputs

**Communication Style** (formal | business | informal):
- Formal: Very polite, structured, traditional business language
- Business: Professional but approachable
- Informal: Casual, friendly, relaxed tone
- Used for draft generation to match sender's style

**Detected Language** (cs | en | de | ...):
- Primary language of the email
- Used to generate draft in same language
- Defaults to Czech (cs) for Czech-language system

**Confidence Level** (high | medium | low):
- Indicates LLM's certainty in classification
- High: Clear, unambiguous classification
- Medium: Some ambiguity but reasonable confidence
- Low: Uncertain, may need human review

**Reasoning**:
- Human-readable explanation of classification decision
- Helps users understand why email was classified a certain way
- Useful for debugging misclassifications

### LLM Model
- Fast, cost-effective model (default: Gemini 2.0 Flash)
- Temperature: 0.0 (deterministic)
- Output format: JSON with strict schema
- Token limit: 256 (classification is concise)

## Style Resolution

The system determines communication style using a priority order:

1. **Exact email match**: Check contacts.style_overrides for exact sender email
2. **Domain pattern match**: Check contacts.domain_overrides for sender domain
3. **LLM-determined style**: Use style detected by LLM during classification
4. **Fallback**: Default to "business" if no match

Example:
```
Sender: important@client.com
1. Check style_overrides["important@client.com"] → formal (MATCH)
2. Use "formal" style for draft generation
```

## Language Resolution

Similar priority order for language:
1. Check contacts.language_overrides for sender email/domain
2. Use LLM-detected language
3. Fallback to default_language (Czech)

## Classification Flow

```
New Email Arrives
    ↓
Tier 1: Rule-Based Check
    ↓
Is Automated? → YES → Mark as "fyi", skip Tier 2
    ↓ NO
Tier 2: LLM Classification
    ↓
Parse JSON Response (category, style, language, confidence, reasoning)
    ↓
Safety Check: If is_automated=true AND category=needs_response → Override to "fyi"
    ↓
Style Resolution (overrides → LLM → default)
    ↓
Store Email Record with Classification
    ↓
Apply Gmail Label (based on category)
    ↓
Log Event (classified)
    ↓
Decision:
├─ needs_response → Enqueue draft job
├─ action_required → Done (label only)
├─ payment_request → Done (label only)
├─ fyi → Done (label only)
└─ waiting → Done (label only)
```

## Reclassification

### Manual Reclassification
- Triggered via: Debug API endpoint `/api/emails/{id}/reclassify`
- Behavior: Re-runs LLM classification with force flag
- Use case: User disagrees with initial classification

### Automatic Reclassification (Waiting Threads)
- Trigger: New reply arrives on thread with "waiting" status
- Behavior: Removes Waiting label, re-runs full classification pipeline
- Detects when external party responds to user's message

### Label Changes
When reclassification changes category:
- Old label removed
- New label added
- If old category was needs_response and new is not: trash any dangling drafts
- Event logged: classified with new category

## Classification Audit

Every classification is logged:
- Email record stores: classification, confidence, reasoning, detected_language, resolved_style
- Event record logged: event_type=classified
- LLM call record logged: prompt, response, tokens, latency
- All data available via debug API for analysis

## Edge Cases

### Multi-Message Threads
- System fetches entire thread context
- LLM sees conversation history
- Detects if user sent last message (waiting classification)

### Paid Invoices
- LLM distinguishes between invoices (needs payment) and receipts (already paid)
- Receipts classified as "fyi", not "payment_request"

### Meeting Invitations
- Calendar invites classified as "action_required"
- No draft generated (user clicks accept/decline in calendar)

### Newsletters with Questions
- If newsletter contains direct question to user: "needs_response"
- If newsletter is just informational: "fyi"
- LLM context-awareness distinguishes

### Ambiguous Emails
- LLM marks confidence as "low"
- Reasoning field explains uncertainty
- User can review via debug interface

## Testing & Validation

### Test Fixture Format
YAML file with test cases:
```yaml
- id: test_001
  category: needs_response
  sender_email: client@example.com
  subject: "Quick question"
  body: "Can you send the report?"
  expected_classification: needs_response
  notes: "Direct question requiring response"
```

### Validation Metrics
- Accuracy: % of correct classifications
- Confusion matrix: Shows which categories are confused
- Tier tracking: % classified by rules vs LLM
- Token usage: Cost tracking per classification

### Debug Tools
- Interactive classifier: Test single email with full output
- Test suite runner: Batch validation against fixtures
- Classification timeline: View LLM prompts and responses for any email
