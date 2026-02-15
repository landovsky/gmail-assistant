# LLM Integration

## LLM Gateway Pattern

### Purpose
Provide model-agnostic LLM access with automatic logging, error handling, and retry logic.

### Architecture
The system uses LiteLLM as a unified gateway to 100+ LLM providers, enabling easy model switching without code changes.

## Supported Operations

### classify()
**Purpose**: Fast email classification with structured JSON output

**Model**: Fast, cost-effective (default: Gemini 2.0 Flash)

**Parameters**:
- Email metadata (sender, subject, body)
- User ID (for logging)
- Thread ID (for logging)

**Temperature**: 0.0 (deterministic)

**Max Tokens**: 256 (classification is concise)

**Output Format**: JSON
```json
{
  "classification": "needs_response",
  "confidence": "high",
  "reasoning": "Sender is asking a direct question...",
  "detected_language": "cs",
  "style": "business"
}
```

**Post-Processing**:
- Strip code fence markers (```json ... ```)
- Parse JSON
- Validate schema
- Extract fields

**Error Handling**:
- Retry on timeout/rate limit
- Log full prompt and response
- Return default on permanent failure

### draft()
**Purpose**: Generate high-quality email draft responses

**Model**: High-quality (default: Gemini 2.5 Pro or Claude Sonnet)

**Parameters**:
- Email thread
- Communication style
- Related context
- User instructions (optional for rework)
- User ID (for logging)
- Thread ID (for logging)

**Temperature**: 0.3 (creative but consistent)

**Max Tokens**: 2048 (allows detailed responses)

**Output Format**: Plain text

**Post-Processing**:
- Append rework marker (✂️)
- MIME encode for Gmail
- Base64 encode

**Error Handling**:
- Retry on transient failures
- Fallback to simpler prompt if context too large
- Log full prompt and response

### generate_context_queries()
**Purpose**: Generate Gmail search queries to find related threads

**Model**: Fast (default: Gemini 2.0 Flash)

**Parameters**:
- Email content (sender, subject, body)
- User ID (for logging)

**Temperature**: 0.0 (deterministic)

**Max Tokens**: 256

**Output Format**: JSON array
```json
{
  "queries": [
    "from:sender@example.com subject:project",
    "subject:budget approval",
    "from:sender@example.com newer_than:7d"
  ]
}
```

**Post-Processing**:
- Strip code fence markers
- Parse JSON
- Extract queries array
- Limit to 3 queries

### agent_completion()
**Purpose**: Agent tool-use loop with function calling

**Model**: Configured per agent profile

**Parameters**:
- System prompt
- Message history
- Available tools (OpenAI function format)
- Max tokens, temperature (profile-specific)

**Output Format**: OpenAI-compatible response
```json
{
  "choices": [
    {
      "message": {
        "content": "text response",
        "tool_calls": [
          {
            "function": {
              "name": "tool_name",
              "arguments": "{\"param\": \"value\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls" | "stop"
    }
  ]
}
```

**Behavior**:
- LLM decides whether to use tools or respond
- Tool calls executed by agent loop
- Results fed back to LLM
- Continues until LLM stops or max iterations

## Model Configuration

### Default Models

**Classification**: gemini/gemini-2.0-flash
- Rationale: Fast, cheap, accurate for classification
- Fallback: claude-3-haiku-20240307

**Drafting**: gemini/gemini-2.5-pro
- Rationale: High quality, supports Czech/English well
- Fallback: claude-sonnet-4

**Context**: gemini/gemini-2.0-flash
- Rationale: Fast query generation
- Fallback: claude-3-haiku-20240307

**Agents**: Configurable per profile
- Example: gemini/gemini-2.5-pro for pharmacy agent

### Model Switching

**Via Configuration**:
```yaml
llm:
  classify_model: "anthropic/claude-3-haiku"
  draft_model: "anthropic/claude-sonnet-4"
  context_model: "openai/gpt-4o-mini"
```

**Via Environment Variables**:
```bash
export GMA_LLM_CLASSIFY_MODEL="anthropic/claude-3-haiku"
export GMA_LLM_DRAFT_MODEL="anthropic/claude-sonnet-4"
```

**Model Format**: `provider/model-name`
- Examples: `anthropic/claude-sonnet-4`, `openai/gpt-4o`, `gemini/gemini-2.5-pro`

## LiteLLM Provider Support

### Supported Providers
- Anthropic (Claude models)
- OpenAI (GPT models)
- Google AI (Gemini models)
- Azure OpenAI
- AWS Bedrock
- Groq
- Together AI
- Replicate
- 100+ more via LiteLLM

### API Key Configuration

**Environment Variables** (LiteLLM standard):
- `ANTHROPIC_API_KEY` - For Claude models
- `OPENAI_API_KEY` - For GPT models
- `GEMINI_API_KEY` - For Gemini models
- `GROQ_API_KEY` - For Groq models
- Etc. (provider-specific)

**Multiple Providers**:
- Set multiple API keys
- Switch models via configuration
- No code changes required

## Automatic Logging

### Purpose
Every LLM call is logged for debugging, cost tracking, and analysis.

### Logged Data

**llm_calls Table**:
- User ID (nullable for system calls)
- Thread ID (if email-related)
- Call type (classify | draft | rework | context | agent)
- Model used
- System prompt (full text)
- User message (full text)
- Response text (full text)
- Prompt tokens
- Completion tokens
- Total tokens
- Latency (milliseconds)
- Error message (if failed)
- Timestamp

### Use Cases

**Cost Tracking**:
- Sum total_tokens grouped by model
- Calculate costs using provider pricing
- Identify expensive operations

**Debugging**:
- View exact prompts sent to LLM
- See raw LLM responses
- Identify prompt engineering issues
- Reproduce classification/draft results

**Performance Analysis**:
- Track latency trends
- Identify slow models/operations
- Optimize prompt sizes

**Quality Analysis**:
- Correlate confidence levels with accuracy
- Find patterns in misclassifications
- Improve prompt templates

## Prompt Engineering

### Classification Prompt Structure

**System Prompt**:
- Role definition (you are an email classifier)
- Task description
- Categories with clear definitions
- Output format requirements (JSON schema)
- Style detection guidelines
- Language detection guidelines

**User Message**:
- Email metadata header
- Sender information
- Subject line
- Email body
- Thread context (if multi-message)

**Best Practices**:
- Clear category definitions with examples
- Explicit JSON schema
- Emphasis on confidence scoring
- Reasoning requirement (explainability)

### Draft Prompt Structure

**System Prompt**:
- Role definition (you are an email assistant)
- Communication style guidelines
- Language instructions
- Tone and formality rules
- Structure guidelines
- Length guidelines
- Prohibited actions (no promises without data)

**User Message**:
- Thread context (full conversation)
- Related context from mailbox
- Communication style template
- Language preference
- User instructions (if rework)

**Best Practices**:
- Rich context (thread + related emails)
- Style examples in prompt
- Clear structure guidance
- Language consistency enforcement

### Context Query Prompt Structure

**System Prompt**:
- Task: Generate Gmail search queries
- Query syntax guidelines
- Limit: Up to 3 queries
- Output format: JSON array

**User Message**:
- Email content to find related threads for
- Examples of good queries

**Best Practices**:
- Gmail search syntax education
- Limit number of queries
- Encourage specific, targeted queries

### Agent Prompt Structure

**System Prompt** (example: pharmacy agent):
- Role definition (you are customer support)
- Service description (pharmacy availability service)
- Available tools (with clear descriptions)
- Decision guidelines (when to auto-send vs draft)
- Communication guidelines (Czech, polite, professional)
- Prohibited actions (no medical advice)

**User Message**:
- Parsed patient information
- Original message
- Context (if available)

**Best Practices**:
- Clear tool use guidelines
- Safety instructions
- Communication style rules
- Escalation criteria

## Error Handling

### Retry Logic

**Transient Errors** (retried):
- Network timeouts
- Rate limits (429)
- Server errors (500, 502, 503, 504)
- Temporary API unavailability

**Permanent Errors** (not retried):
- Invalid API key (401)
- Model not found (404)
- Invalid request (400)
- Content policy violation

**Retry Parameters**:
- Max attempts: 3
- Backoff strategy: Exponential (provider-dependent)
- Total timeout: 60 seconds

### Fallback Strategies

**Model Fallback**:
- If primary model fails → try fallback model
- Example: gemini-2.5-pro → claude-sonnet-4

**Prompt Simplification**:
- If context too large → truncate related context
- If still too large → remove related context entirely
- Preserve core email content

**Graceful Degradation**:
- Classification failure → mark as "fyi" with low confidence
- Draft failure → log error, retry job
- Context query failure → proceed without related context

## Token Usage Optimization

### Classification
- Use fast, cheap model
- Short prompts (email content only)
- Concise system prompt
- Max tokens: 256 (classification is brief)

### Drafting
- Use quality model (worth the cost)
- Rich context (thread + related emails)
- Detailed system prompt with examples
- Max tokens: 2048 (responses can be detailed)

### Context Gathering
- Use fast, cheap model
- Brief prompts
- Max tokens: 256 (just generating queries)

### Cost Estimation

**Per Email (Classification + Draft)**:
- Classification: ~500 input + 100 output tokens
- Context gathering: ~500 input + 50 output tokens
- Draft: ~2000 input + 500 output tokens
- **Total**: ~3000 input + 650 output tokens

**Gemini Pricing Example** (as of 2025):
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens
- Cost per email: ~$0.0004 (0.04 cents)

**Claude Pricing Example** (as of 2025):
- Haiku input: $0.25 per 1M tokens
- Haiku output: $1.25 per 1M tokens
- Sonnet input: $3 per 1M tokens
- Sonnet output: $15 per 1M tokens
- Cost per email (Haiku classify + Sonnet draft): ~$0.012 (1.2 cents)

## Prompt Templates

### Template Storage
- System prompts: Text files in `config/prompts/`
- Classification prompt: Embedded in code (frequently updated)
- Draft prompt: Embedded in code (with style templates)
- Agent prompts: Text files (pharmacy.txt, etc.)

### Template Variables
- Placeholders: `{variable_name}`
- Populated at runtime with email data
- Examples: `{sender_email}`, `{subject}`, `{body}`, `{style}`

### Template Versioning
- Prompts evolve over time
- Git tracks changes
- LLM call logs preserve prompts used
- Can reproduce old results with old prompts

## Output Validation

### JSON Response Validation

**Classification Output**:
- Required fields: classification, confidence, reasoning
- Optional fields: detected_language, style
- Validation: Pydantic models
- Fallback: Default values on parse error

**Context Query Output**:
- Required field: queries (array of strings)
- Validation: JSON parse + array check
- Fallback: Empty array

### Error Recovery

**Invalid JSON**:
- Strip common artifacts (code fences, extra text)
- Attempt re-parse
- Log warning
- Use defaults

**Missing Fields**:
- Use sensible defaults
- Log warning
- Continue processing

**Invalid Enum Values**:
- Map to closest valid value
- Log warning
- Avoid hard failures

## Model Performance Monitoring

### Metrics Tracked
- Latency per model and operation
- Token usage per model and operation
- Error rates per model
- Cost per email processed

### Debug Access
- API endpoint: `/api/emails/{id}/debug`
- Shows all LLM calls for an email
- Expandable prompts and responses
- Token counts and latency

### Optimization Opportunities
- Slow models → switch to faster alternatives
- Expensive operations → prompt size reduction
- High error rates → model or prompt issues
- Token waste → prompt optimization
