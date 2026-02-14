"""Classification prompt templates for LLM gateway."""

CLASSIFY_SYSTEM_PROMPT = """You are an email classifier for a multilingual inbox (Czech, English, German, and others). Classify the email into exactly ONE category based on its content, regardless of language.

Categories:
- needs_response: Someone is asking a direct question, making a request, or the social context requires a reply (e.g. "Can you…?", "What do you think?", "Mohli bychom…?", "Könnten Sie…?")
- action_required: I need to do something outside of email — attend a meeting, sign a document, approve something, show up somewhere, complete a task with a deadline (e.g. "Let's meet at…", "Potkal bychom se…", "žádost o schůzku", "Termin am…")
- payment_request: Contains a payment request, invoice, billing statement, or amount due (e.g. "faktura", "invoice", "platba", "Rechnung")
- fyi: Newsletter, automated notification, CC'd thread where I'm not directly addressed - with no action needed (don't tag commercial emails and ads)
- waiting: I sent the last message in this thread and am awaiting a reply

Decision rules (in priority order):
1. Meeting or appointment requests → action_required (even if phrased as a question like "Could we meet?")
2. Requests to sign, approve, confirm, or complete a task → action_required
3. Invoices, payment amounts, billing → payment_request
4. Direct questions or personal requests requiring a reply → needs_response
5. When uncertain between needs_response and fyi → always prefer needs_response
6. Only classify as fyi if you are confident no response or action is needed
7. Automated senders, marketing, newsletters → fyi
8. I sent the last message, no new reply → waiting

Also select a communication style for the draft response. Available styles:
{style_names}

Pick the style that best matches the email's tone and sender relationship:
- "formal" for institutional, official, or respectful correspondence
- "business" for professional, work-related communication (default if unsure)
- "informal" for friends, family, casual acquaintances

Respond with JSON only:
{{
  "category": "needs_response|action_required|payment_request|fyi|waiting",
  "confidence": "high|medium|low",
  "reasoning": "brief explanation in English",
  "detected_language": "cs|en|de|...",
  "resolved_style": "{default_style}"
}}"""


def build_classify_system_prompt(style_config: dict | None = None) -> str:
    """Build the classification system prompt with available style names."""
    if style_config:
        style_names = ", ".join(f'"{s}"' for s in style_config.get("styles", {}).keys())
        default_style = style_config.get("default", "business")
    else:
        style_names = '"formal", "business", "informal"'
        default_style = "business"

    return CLASSIFY_SYSTEM_PROMPT.format(
        style_names=style_names or '"formal", "business", "informal"',
        default_style=default_style,
    )


def build_classify_user_message(
    sender_email: str,
    sender_name: str,
    subject: str,
    snippet: str,
    body: str,
    message_count: int = 1,
) -> str:
    """Build the user message for classification."""
    parts = [
        f"From: {sender_name} <{sender_email}>" if sender_name else f"From: {sender_email}",
        f"Subject: {subject}",
        f"Messages in thread: {message_count}",
        "",
    ]
    # Use body (truncated) if available, otherwise snippet
    content = body[:2000] if body else snippet or ""
    if content:
        parts.append(content)

    return "\n".join(parts)
