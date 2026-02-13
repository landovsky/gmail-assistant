# Plan: Agent Processing Architecture

## Context

The Gmail Assistant currently handles a personal inbox with a rigid pipeline (classify → draft). A new use case has emerged: **pharmacy support emails** from patients via Crisp (forwarded to Gmail from info@dostupnost-leku.cz). These need agentic processing — Claude looks up drug availability via the dostupnost-leku.cz API, searches the web for drug info, and composes informed replies. Simple queries auto-send; complex ones go to draft for review.

Rather than building a one-off, we're adding a **routing + agent framework** to the existing system so both use cases (and future ones) share infrastructure (DB, audit, admin, jobs).

## Architecture

```
Email arrives → Sync Engine
                    ↓
              Route Decision (config-based rules)
                    ↓
         ┌─────────┴──────────┐
         ↓                    ↓
   default route         agent route
         ↓                    ↓
   Preprocessor          Preprocessor
   (rules engine)        (parse Crisp format)
         ↓                    ↓
   Current pipeline      Agent Loop
   (classify → draft)    (Claude + tools)
```

**Key principle**: Every route has a preprocessor (algorithmic, no LLM) → then a handler (current pipeline OR agent with tools).

## Implementation Phases

### Phase 1: Agent Framework (`src/agent/`)

New module with the core agent loop:

- **`src/agent/loop.py`** — Tool-use loop: call Claude → execute tool calls → feed results back → repeat until done or max iterations
- **`src/agent/tools.py`** — Tool interface: `@dataclass Tool(name, description, parameters, handler)`. Registry pattern for tool lookup.
- **`src/agent/profile.py`** — Agent profile: system prompt, available tools, model, temperature, max iterations, auto-send rules

Extend **`src/llm/gateway.py`** — Add `agent_completion()` method that passes `tools` param to `litellm.completion()` and returns the message with tool_calls.

### Phase 2: Routing (`src/routing/`)

- **`src/routing/router.py`** — `Router.route(message) -> RoutingDecision(route_name, profile_name, metadata)`
- **`src/routing/rules.py`** — Config-driven rules: match on sender, domain, subject, headers, forwarding patterns
- **Config** (`config/app.yml`):
  ```yaml
  routing:
    rules:
      - name: pharmacy_support
        match:
          forwarded_from: "info@dostupnost-leku.cz"
          # or: sender_domain, subject_contains, header_match
        route: agent
        profile: pharmacy
      - name: default
        match: { all: true }
        route: pipeline  # current classify→draft
  ```
- **`src/config.py`** — Add `RoutingConfig` and `AgentConfig` to `AppConfig`

### Phase 3: Preprocessing Layer (`src/routing/preprocessors/`)

- **Interface**: `Preprocessor.process(raw_message) -> ProcessedMessage` (extracts structured data before agent/pipeline)
- **`crisp.py`** — Parse Crisp forwarding format: extract patient name, original message, contact info
- **`default.py`** — Pass-through (or current rules engine output for the default route)
- Wire into sync engine: `_process_history_record()` checks routing rules before queuing either `classify` or `agent_process` job

### Phase 4: Pharmacy Agent Profile

**Tools to implement** (in `src/agent/tools/`):

| Tool | Description | Implementation |
|------|-------------|----------------|
| `search_drugs` | Query dostupnost-leku.cz API for drug availability | HTTP call to their REST API |
| `manage_reservation` | Create/check/cancel drug reservations | HTTP call to their REST API |
| `web_search` | Search web for drug-related information | Web search API (to decide: Tavily, SerpAPI, or similar) |
| `send_reply` | Auto-send reply to patient (simple queries) | Gmail API send |
| `create_draft` | Create draft for review (complex queries) | Gmail API draft + outbox label |
| `escalate` | Flag for human review | Apply action_required label |

**System prompt**: Czech-language pharmacy assistant, knows dostupnost-leku.cz capabilities, healthcare-appropriate tone, knows when to escalate.

**Auto-send decision**: The agent itself decides based on confidence. System prompt instructs: "Use `send_reply` for straightforward drug availability queries where you're confident. Use `create_draft` for reservations, complaints, or anything you're unsure about. Use `escalate` for medical advice requests or anything outside scope."

### Phase 5: Worker Integration & Audit

- **`src/tasks/workers.py`** — Add `_handle_agent_process()` handler, dispatched when `job.job_type == "agent_process"`
- **DB migration** — `agent_runs` table: `id, user_id, gmail_thread_id, profile, status, tool_calls_log (JSON), result, error, created_at, completed_at`
- **`src/db/models.py`** — Add `AgentRunRepository` with create/log/complete methods
- **`email_events`** — Log agent events (routed, processed, auto-sent, escalated) for existing audit trail

## Files to Create/Modify

**New files:**
- `src/agent/__init__.py`
- `src/agent/loop.py` — Agent execution loop
- `src/agent/tools.py` — Tool interface + registry
- `src/agent/profile.py` — Agent profile dataclass
- `src/agent/tools/__init__.py`
- `src/agent/tools/pharmacy.py` — Pharmacy-specific tools
- `src/routing/__init__.py`
- `src/routing/router.py` — Route decision logic
- `src/routing/rules.py` — Config-driven matching rules
- `src/routing/preprocessors/__init__.py`
- `src/routing/preprocessors/crisp.py` — Crisp email parser
- `src/routing/preprocessors/default.py` — Pass-through
- `src/db/migrations/002_agent_runs.sql`

**Modified files:**
- `src/llm/gateway.py` — Add `agent_completion()` method
- `src/sync/engine.py` — Add routing decision before job dispatch
- `src/tasks/workers.py` — Add `_handle_agent_process()` handler
- `src/config.py` — Add `RoutingConfig`, `AgentConfig`
- `config/app.yml` — Add routing rules + agent profiles config
- `src/db/models.py` — Add `AgentRunRepository`

## Verification

1. **Unit tests**: Agent loop with mock tools, routing rules matching, Crisp preprocessor parsing
2. **Integration test**: Send a test email mimicking Crisp forwarding format → verify it routes to agent → verify tool calls → verify draft/reply created
3. **Manual test**: Use `/send-test-email` skill to send a Crisp-style email, watch it flow through the system
4. **Admin check**: Verify `agent_runs` table logs the full tool call chain for debugging

## Approach: Stub-First

All pharmacy tools (`search_drugs`, `manage_reservation`, `web_search`) will be **stubbed** with realistic mock responses. This lets us build and test the full agent framework end-to-end without external dependencies. Real API integration comes later when API docs are available.

Web search provider TBD — stubbed for now.

## Open Question

- **Crisp email format**: Need a sample forwarded email to build the parser correctly. Can work with a real example from Gmail or a description of the format.
