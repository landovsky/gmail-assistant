# 07 — Agent Framework & Routing

## Overview

The agent framework provides an alternative processing path for emails that match specific routing rules. Instead of the standard classify→draft pipeline, matched emails are processed by an LLM agent that can use registered tools in a multi-turn conversation loop. Routing is config-driven — rules match on sender, domain, subject, headers, or forwarding patterns.

---

## Routing

### How Routing Works

When the sync engine encounters a new INBOX message, it checks routing rules (if a router is configured). Rules are evaluated in order; the first match wins.

**Route outcomes:**
- `pipeline` (default) — Standard classify→draft flow. Enqueues a `classify` job.
- `agent` — Agent processing. Enqueues an `agent_process` job with the matched profile name.

If no rules match or no router is configured, the default is `pipeline`.

### Routing Rules

Each rule specifies:
- **name** — Identifier for audit logging
- **match** — Conditions dictionary (all specified conditions must match)
- **route** — `pipeline` or `agent`
- **profile** — Agent profile name (required when route is `agent`)

### Match Conditions

| Condition | Type | Behavior |
|-----------|------|----------|
| `all: true` | boolean | Catch-all — matches every email |
| `sender_email` | string | Exact match on sender email address |
| `sender_domain` | string | Exact match on sender's domain (after @) |
| `subject_contains` | string | Case-insensitive substring match on subject |
| `header_match` | object | Dict of `{header_name: regex_pattern}`. All specified headers must match. |
| `forwarded_from` | string | Detects forwarded emails. Checks multiple signals: `X-Forwarded-From` header, `Reply-To` header, email pattern in body, and sender email directly. |

When multiple conditions are specified in a single rule, ALL must match (AND logic).

### Routing Configuration Example

```yaml
routing:
  rules:
    - name: pharmacy_support
      match:
        forwarded_from: "info@dostupnost-leku.cz"
      route: agent
      profile: pharmacy
    - name: default
      match:
        all: true
      route: pipeline
```

---

## Agent Profiles

Each agent profile defines the LLM configuration, available tools, and system prompt for a specific domain.

### Profile Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| name | string | required | Profile identifier |
| model | string | `gemini/gemini-2.5-pro` | LLM model identifier |
| max_tokens | integer | 4096 | Max tokens per LLM response |
| temperature | float | 0.3 | Sampling temperature |
| max_iterations | integer | 10 | Maximum tool-use loop iterations |
| system_prompt_file | string | required | Path to system prompt text file |
| tools | list[string] | required | List of tool names available to this agent |

### Profile Configuration Example

```yaml
agent:
  profiles:
    pharmacy:
      model: gemini/gemini-2.5-pro
      max_tokens: 4096
      temperature: 0.3
      max_iterations: 10
      system_prompt_file: config/prompts/pharmacy.txt
      tools:
        - search_drugs
        - manage_reservation
        - web_search
        - send_reply
        - create_draft
        - escalate
```

---

## Agent Loop

### Execution Flow

The agent loop implements a standard tool-use pattern:

```
1. Build initial messages:
   - System message (from profile's system prompt)
   - User message (preprocessed email content)

2. For each iteration (up to max_iterations):
   a. Call LLM with messages + tool specifications
   b. Append assistant response to conversation
   c. If NO tool calls in response → agent is done → return "completed"
   d. For each tool call:
      - Parse tool name and arguments
      - Execute tool via registry
      - Record the tool call (name, arguments, result, iteration)
      - Append tool result to conversation
   e. Continue to next iteration

3. If max_iterations exhausted → return "max_iterations"
```

### Agent Result

Each agent run produces:
- **status**: `completed` (agent finished voluntarily), `max_iterations` (hit limit), `error` (LLM call failed)
- **final_message**: The last text content from the assistant
- **tool_calls**: List of all tool calls made, each with: tool_name, arguments, result, iteration number
- **iterations**: Total number of LLM turns
- **error**: Error message (if status is `error`)

### LLM Call Format

Tool specifications are provided in the OpenAI function-calling format:

```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "What the tool does",
    "parameters": {
      "type": "object",
      "properties": {
        "param1": {"type": "string", "description": "..."},
        "param2": {"type": "integer", "default": 5}
      },
      "required": ["param1"]
    }
  }
}
```

The LLM responds with tool calls:
```json
{
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "tool_name",
        "arguments": "{\"param1\": \"value\"}"
      }
    }
  ]
}
```

Tool results are fed back as:
```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "{\"result\": \"data\"}"
}
```

### Error Handling

- **LLM call failure:** Returns immediately with status `error` and the exception message
- **Tool execution failure:** The tool registry catches exceptions and returns `{"error": "message"}` as the tool result. The agent loop continues (the LLM can decide how to handle the error).
- **JSON parse failure for tool arguments:** Defaults to empty object `{}`

---

## Tool Registry

### Design

The tool registry manages available tools and provides:
- **Registration:** Tools are registered with a name, description, parameter schema, and handler function
- **Spec generation:** Converts registered tools to OpenAI function-calling format for the LLM
- **Execution:** Looks up a tool by name and calls its handler with parsed arguments
- **Filtering:** Can return specs for a subset of tools (by name list) so different agent profiles see different tools

### Tool Definition

Each tool has:
- **name** — Unique string identifier
- **description** — Natural language description for the LLM
- **parameters** — JSON Schema object defining accepted arguments
- **handler** — Callable that receives keyword arguments and returns a result

### Registered Tools (Pharmacy Domain)

The current implementation includes stubbed tools for a pharmacy domain:

| Tool | Purpose | Parameters | Notes |
|------|---------|------------|-------|
| `search_drugs` | Search drug availability database | `query` (string, required), `limit` (integer, default 5) | Returns mock data — real API integration pending |
| `manage_reservation` | Create/check/cancel drug reservations | `action` (string: create/check/cancel), `drug_name` (string), `pharmacy_id` (string, optional) | Returns mock data |
| `web_search` | General web search for drug information | `query` (string, required) | Returns mock data |
| `send_reply` | Send an email reply | `to` (string), `subject` (string), `body` (string) | Stubbed — returns confirmation without sending |
| `create_draft` | Create a draft for human review | `to` (string), `subject` (string), `body` (string) | Stubbed — returns confirmation without creating |
| `escalate` | Flag conversation for human review | `reason` (string, required) | Stubbed — returns confirmation |

[UNCLEAR: All pharmacy tools currently return mock/stub data. The actual external API integrations have not been implemented.]

---

## Preprocessors

Before an email reaches the agent loop, it may be preprocessed to extract structured data.

### Default Preprocessor

Pass-through — returns the email content unchanged as sender_email, subject, and body.

### Crisp Preprocessor

Parses emails forwarded by the Crisp helpdesk platform. Extracts:
- **patient_name** — Customer name from Crisp formatting
- **patient_email** — Customer email address
- **original_message** — The actual customer message (stripped of Crisp headers/footers)

Uses regex patterns to identify Crisp formatting and extract structured fields. Supports Czech and English Crisp headers.

The preprocessor formats the extracted data into a structured prompt for the agent:
```
New support inquiry from {patient_name} ({patient_email}):
Subject: {subject}

{original_message}
```

---

## Audit Trail

Agent executions are tracked in two places:

1. **agent_runs table** — One row per execution with profile, status, tool_calls_log (JSON), final_message, iterations, error
2. **llm_calls table** — One row per LLM turn within the agent loop (call_type=`agent`)
3. **email_events table** — Summary event logged after completion

The `tool_calls_log` in `agent_runs` is a JSON array:
```json
[
  {
    "tool": "search_drugs",
    "arguments": {"query": "ibuprofen"},
    "result": {"drugs": [...]},
    "iteration": 1
  },
  {
    "tool": "create_draft",
    "arguments": {"to": "...", "subject": "...", "body": "..."},
    "result": {"status": "created"},
    "iteration": 2
  }
]
```
