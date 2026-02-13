# Classification and Drafting

## Two-Tier Classification Engine

Located in `src/classify/`.

### Tier 1: Rule Engine (`rules.py`)
Deterministic pattern matching — instant, free, no LLM calls.

Matches on:
- **Sender patterns**: `noreply@`, `no-reply@`, known newsletter domains
- **Subject patterns**: "unsubscribe", "receipt", "invoice", "digest"
- **Keyword patterns**: payment indicators, notification types

Returns classification + confidence. If confidence is "low", falls through to Tier 2.

### Tier 2: LLM Classification (`engine.py` + `prompts.py`)
Uses LiteLLM gateway with the classify model (default: Claude Haiku).

**System prompt** instructs the LLM to:
- Classify into one of: `needs_response`, `action_required`, `payment_request`, `fyi`, `waiting`
- Return confidence: `high`, `medium`, `low`
- Detect language (default: `cs` for Czech)
- Resolve communication style from contacts.yml
- Provide reasoning for the classification

**Response format**: JSON parsed from LLM output.

### Categories

| Category | Description | Draft? |
|----------|-------------|--------|
| `needs_response` | Requires a reply | Yes |
| `action_required` | Non-email action needed | No |
| `payment_request` | Invoice or payment | No |
| `fyi` | Informational only | No |
| `waiting` | Waiting for external reply | No |

## Draft Generation Engine

Located in `src/draft/`.

### Draft Flow
1. Worker picks up `draft` job for `needs_response` emails
2. `DraftEngine.generate()` calls LLM (default: Claude Sonnet)
3. System prompt provides: sender context, style profile, language, thread history
4. LLM returns draft body text
5. Gmail draft created with `In-Reply-To` headers
6. Email status updated to `drafted`, `🤖 AI/Outbox` label applied

### Rework Flow
1. User writes instructions above `✂️` marker in Gmail draft
2. User labels thread with `🤖 AI/Rework`
3. Worker detects rework, reads user instructions
4. `DraftEngine.rework()` generates new draft with instructions
5. Old draft trashed (via `modify_email` + TRASH label), new draft created
6. Up to 3 rework iterations; 3rd attempt includes "last automatic attempt" warning

### Draft Marker Convention
```
User's rework instructions go here

✂️
```
Two blank lines above `✂️`. System reads everything above the marker as instructions.

## LLM Gateway

Located in `src/llm/`.

### Configuration (`config.py`)
```python
classify_model: str = "claude-haiku-4-5-20251001"  # Fast, cheap
draft_model: str = "claude-sonnet-4-5-20250929"     # Higher quality
max_classify_tokens: int = 256
max_draft_tokens: int = 2048
```

Override via env vars: `GMA_LLM_CLASSIFY_MODEL`, `GMA_LLM_DRAFT_MODEL`.

### Gateway Interface (`gateway.py`)
```python
class LLMGateway:
    async def classify(self, system_prompt: str, user_prompt: str) -> dict:
        """Returns parsed JSON: classification, confidence, reasoning, language, style."""

    async def draft(self, system_prompt: str, user_prompt: str) -> str:
        """Returns draft email body text."""

    async def health_check(self) -> bool:
        """Verifies model availability."""
```

### Style Resolution
`config/contacts.yml` maps sender domains/emails to communication styles.
`config/communication_styles.yml` defines tone profiles (formal, casual, etc.).

The resolved style is passed to the draft prompt to match the appropriate tone.

## Lifecycle Manager

Located in `src/lifecycle/manager.py`. **Zero LLM calls** — pure deterministic logic.

### Transitions
- **Done**: User labels with `🤖 AI/Done` → remove other AI labels, archive, keep Done marker
- **Sent**: Draft disappears from Gmail Drafts → detect sent, update status
- **Waiting re-triage**: Reply detected on `waiting` thread → re-classify
- **Rework**: `🤖 AI/Rework` label detected → create rework job

### Safety Guarantees
- Never sends emails automatically
- Never deletes emails (uses TRASH label, recoverable 30 days)
- All transitions logged to `email_events` audit table
- `🤖 AI/Done` label is permanent (never removed) — serves as audit trail
