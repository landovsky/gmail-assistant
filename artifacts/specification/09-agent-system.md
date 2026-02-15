# Agent Framework and Routing System

## Purpose

The agent system enables LLM-powered autonomous email handling for specific use cases where:
- Standard classify→draft pipeline is insufficient
- Domain-specific tools/actions are needed
- Auto-sending (without human review) is acceptable
- Complex multi-step workflows are required

## Agent Architecture

### Agent Loop

The core agent loop implements tool-use pattern:

**Process**:
1. Initialize with system prompt and user message
2. Call LLM with available tools
3. If LLM requests tool use:
   - Execute tool with provided arguments
   - Add tool result to conversation
   - Loop back to step 2
4. If LLM provides final answer or reaches max iterations:
   - Return result
5. Continue until completion, error, or max iterations

**Configuration**:
- Max iterations: Prevents infinite loops (default: 10)
- Model: LLM to use (configurable per profile)
- Temperature: Controls randomness (configurable per profile)
- Max tokens: Response length limit (configurable per profile)

**Output**:
- Status: completed | error | max_iterations
- Final message: Agent's concluding response
- Tool calls log: JSON array of all tool invocations
- Iterations count: Number of loop cycles

### Tool Registry

**Purpose**: Central registry of all tools available to agents

**Tool Definition**:
- Name: Unique identifier
- Description: What the tool does (shown to LLM)
- Parameters: JSON schema defining inputs
- Handler: Function that executes the tool

**Tool Schema Format** (OpenAI-compatible):
```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "What this tool does",
    "parameters": {
      "type": "object",
      "properties": {
        "param1": {
          "type": "string",
          "description": "First parameter"
        }
      },
      "required": ["param1"]
    }
  }
}
```

**Tool Execution**:
- Tools called by name with validated arguments
- Tool handlers receive user_id and tool-specific params
- Tools return result as string
- Errors caught and returned to LLM as tool result

### Agent Profiles

**Purpose**: Configuration templates for different agent types

**Profile Attributes**:
- Model: Which LLM to use
- System prompt file: Path to system prompt template
- Tools: List of tool names available to this agent
- Temperature: Creativity setting
- Max tokens: Response length
- Max iterations: Loop limit

**Profile Configuration** (YAML):
```yaml
profiles:
  pharmacy:
    model: "gemini/gemini-2.5-pro"
    max_tokens: 4096
    temperature: 0.3
    max_iterations: 10
    system_prompt_file: "config/prompts/pharmacy.txt"
    tools:
      - search_drugs
      - manage_reservation
      - web_search
      - send_reply
      - create_draft
      - escalate
```

## Routing System

### Purpose
Decide which emails go to standard pipeline vs. agent processing.

### Routing Decision

**Input**: Email metadata (sender, subject, headers, body)

**Output**: Route decision
- Route name: "pipeline" or "agent"
- Profile name: Agent profile to use (if agent route)
- Rule name: Which rule matched
- Metadata: Additional context

### Routing Rules

Rules defined in configuration, evaluated in order (first match wins):

**Match Criteria** (all must pass for rule to match):

**all: true**
- Catch-all rule
- Matches every email
- Typically used as final fallback rule

**forwarded_from**
- Checks multiple sources for forwarder:
  - Sender email address
  - X-Forwarded-From header
  - Reply-To header
  - Body text patterns (From:, Od:, etc.)
- Use case: Emails forwarded from helpdesk systems
- Example: `forwarded_from: "info@support-system.com"`

**sender_domain**
- Domain portion of sender email
- Case-insensitive match
- Example: `sender_domain: "client.com"`

**sender_email**
- Exact sender email address
- Case-insensitive match
- Example: `sender_email: "vip@client.com"`

**subject_contains**
- Substring match in subject line
- Case-insensitive
- Example: `subject_contains: "URGENT"`

**header_match**
- Regex match on specific headers
- Example: `{"X-Priority": "1"}`

### Example Routing Config

```yaml
routing:
  rules:
    - name: pharmacy_support
      match:
        forwarded_from: "info@dostupnost-leku.cz"
      route: agent
      profile: pharmacy

    - name: vip_client
      match:
        sender_domain: "important-client.com"
      route: agent
      profile: vip_handler

    - name: urgent_emails
      match:
        subject_contains: "URGENT"
      route: agent
      profile: urgent_handler

    - name: default
      match:
        all: true
      route: pipeline
```

### Routing Integration Point

Routing happens in sync engine when new messages arrive:

**Process**:
1. Gmail History API detects new inbox message
2. Sync engine fetches message metadata
3. Router evaluates message against rules
4. If route=pipeline:
   - Enqueue classify job
   - Traditional classification → draft flow
5. If route=agent:
   - Enqueue agent_process job with profile name
   - Agent loop with tools

## Preprocessors

### Purpose
Extract structured data from forwarded emails before agent processing.

### Crisp Preprocessor

**Use Case**: Emails forwarded from Crisp helpdesk

**Extraction**:
- Patient name: From "From:" or "Name:" lines in body
- Patient email: From Reply-To header, body, or X-Forwarded-From
- Original message: Strips forwarding metadata

**Detection Patterns**:
- Name patterns: `/(From|Od|Name|Jméno):\s*(.+)/i`
- Separator: `/-{3,}|={3,}|_{3,}/`
- Email: Standard email regex

**Output Format**:
```
Subject: Original subject
Patient name: Jan Novák
Patient email: jan@example.com

Message:
[Original message text]
```

### Default Preprocessor

Simple pass-through for standard emails (no preprocessing needed).

### Future Extensibility

Architecture supports route-specific preprocessors:
- Each routing rule could specify preprocessor
- Preprocessors could be chained
- Custom preprocessors for different forwarding systems

## Available Tools

### Pharmacy Tools (Example Agent)

All tools return string results for LLM consumption:

**search_drugs**
- **Purpose**: Query drug availability on pharmacy database
- **Inputs**: drug_name (string)
- **Output**: Availability information as text
- **Auto-action**: No (read-only query)
- **Current status**: Stubbed (returns mock data)

**manage_reservation**
- **Purpose**: Create/check/cancel pharmacy reservations
- **Inputs**: action (create|check|cancel), drug_name (string), patient_name (string), patient_email (string)
- **Output**: Confirmation message
- **Auto-action**: Yes (creates reservation)
- **Current status**: Stubbed (returns mock data)

**web_search**
- **Purpose**: Search for drug information, side effects, interactions
- **Inputs**: query (string)
- **Output**: Search results as text
- **Auto-action**: No (read-only query)
- **Current status**: Stubbed (returns mock data)

**send_reply**
- **Purpose**: Auto-send reply to patient (no human review)
- **Inputs**: message (string), thread_id (string)
- **Output**: Confirmation that email was sent
- **Auto-action**: Yes (sends email immediately)
- **Safety**: Use only for straightforward queries with high confidence

**create_draft**
- **Purpose**: Create draft for human review before sending
- **Inputs**: message (string), thread_id (string)
- **Output**: Confirmation that draft was created
- **Auto-action**: No (creates draft for review)
- **Safety**: Safe for all scenarios requiring human judgment

**escalate**
- **Purpose**: Flag message for human attention
- **Inputs**: reason (string), thread_id (string)
- **Output**: Confirmation that thread was escalated
- **Auto-action**: Yes (applies Action Required label)
- **Safety**: Safe escalation path

### Tool Decision Guidelines

The pharmacy agent is instructed via system prompt:

**Use send_reply for**:
- Straightforward drug availability queries
- High confidence in answer
- No reservations or complex actions needed
- Standard informational requests

**Use create_draft for**:
- Reservation requests
- Complaints or sensitive issues
- Complex queries requiring nuance
- Any uncertainty about appropriate response

**Use escalate for**:
- Medical advice requests (out of scope)
- Issues beyond agent capabilities
- Customer disputes
- Unclear or ambiguous requests

## Agent Execution Flow

### Trigger

```
New Email Arrives
    ↓
Sync Engine
    ↓
Router Evaluates
    ↓
Match: forwarded_from = "info@dostupnost-leku.cz"
    ↓
Route: agent, Profile: pharmacy
    ↓
Enqueue agent_process job
```

### Job Processing

```
Worker Claims Job
    ↓
Fetch Email Thread from Gmail
    ↓
Run Preprocessor (Crisp parser)
    ↓
Extract: patient name, email, message
    ↓
Create Agent Run Record (status: running)
    ↓
Initialize Agent Loop
    ↓
Load Pharmacy Profile
    ↓
Load System Prompt
    ↓
Format User Message with Patient Info
    ↓
Execute Agent Loop (max 10 iterations)
    ↓
Agent Uses Tools:
  - search_drugs("Ibuprofen 400mg")
  - send_reply("We have it in stock...") OR create_draft(...)
    ↓
Agent Returns Final Message
    ↓
Update Agent Run (status: completed, tool_calls_log, final_message)
    ↓
Log Event (agent_process_completed)
    ↓
Job Complete
```

### Iteration Example

**Iteration 1**:
- LLM: "I need to check drug availability"
- Tool call: search_drugs("Ibuprofen 400mg")
- Tool result: "Available at 3 pharmacies in Prague"

**Iteration 2**:
- LLM: "The drug is available. I'll send a reply."
- Tool call: send_reply("Dobrý den, máme Ibuprofen 400mg...")
- Tool result: "Email sent successfully"

**Iteration 3**:
- LLM: "Task complete"
- Final message: "Responded to patient inquiry about Ibuprofen"
- Status: completed

## Audit and Logging

### Agent Runs Table
Every agent execution logged:
- User ID, thread ID, profile name
- Status (running, completed, error, max_iterations)
- Tool calls log (JSON array)
- Final message
- Iterations count
- Error message (if failed)
- Timestamps (created_at, completed_at)

### Tool Call Log Format
```json
[
  {
    "tool": "search_drugs",
    "arguments": {"drug_name": "Ibuprofen 400mg"},
    "result": "Available at 3 pharmacies...",
    "timestamp": "2025-01-15T10:30:00"
  },
  {
    "tool": "send_reply",
    "arguments": {"message": "Dobrý den..."},
    "result": "Email sent successfully",
    "timestamp": "2025-01-15T10:30:05"
  }
]
```

### Email Events
Agent actions logged as events:
- agent_started
- agent_completed
- agent_error
- reply_sent (if send_reply used)
- draft_created (if create_draft used)
- escalated (if escalate used)

## Safety and Control

### Auto-Send Restriction
- Only specific agent profiles can auto-send
- System prompt clearly defines when to use send_reply vs create_draft
- LLM instructed to err on side of caution (create_draft if uncertain)

### Human Oversight
- All agent runs logged with full detail
- Agents can create drafts for review
- Escalation path always available
- Users can disable agent processing via routing rules

### Error Handling
- Agent loop errors caught and logged
- Max iterations prevents infinite loops
- Tool errors returned to LLM as results
- Failed agent runs marked with error status

## Extensibility

### Adding New Agent Profiles
1. Write system prompt file
2. Implement profile-specific tools
3. Register tools in tool registry
4. Add profile to configuration
5. Add routing rule to match relevant emails

### Adding New Tools
1. Define tool schema (name, description, parameters)
2. Implement tool handler function
3. Register in tool registry
4. Add to relevant agent profile configurations
5. Document in system prompt

### Custom Preprocessors
1. Implement preprocessor class
2. Define extraction patterns
3. Add format_for_agent method
4. Configure in routing rules (future feature)

## Example Agent Profiles (Future)

**VIP Handler**:
- Tools: escalate, create_draft, search_crm
- Purpose: Ensure VIP clients get white-glove service
- Auto-send: Never (always creates drafts)

**Urgent Handler**:
- Tools: create_draft, notify_admin, escalate
- Purpose: Fast-track urgent issues
- Auto-send: Only for acknowledgments

**Invoice Processor**:
- Tools: extract_invoice_data, update_accounting, create_draft
- Purpose: Process payment requests automatically
- Auto-send: Only for confirmations

## Agent vs Pipeline Decision

**Use Agent When**:
- Domain-specific actions needed (reservations, lookups, etc.)
- Auto-sending is acceptable and safe
- Multi-step workflow required
- External tool integration needed
- Complex decision trees

**Use Pipeline When**:
- Standard email response generation
- Human review required for all responses
- No special tools needed
- Simple classification and drafting sufficient
