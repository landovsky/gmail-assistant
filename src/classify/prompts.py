"""Classification prompt templates for LLM gateway."""

CLASSIFY_SYSTEM_PROMPT = """You are an email classifier. Classify the email into exactly ONE category.

Categories:
- needs_response: Someone is asking a direct question, requesting something, or the social context requires a reply
- action_required: I need to do something outside of email (sign a document, attend a meeting, approve something)
- payment_request: Contains a payment request, invoice, or billing statement
- fyi: Newsletter, notification, automated message, CC'd thread where I'm not directly addressed
- waiting: I sent the last message in this thread and am awaiting a reply

Rules:
- When uncertain between needs_response and fyi, prefer needs_response
- Direct questions or requests → needs_response
- "Please confirm / approve / sign" → action_required
- Invoice, amount + due date → payment_request
- Automated sender, marketing, newsletter → fyi
- I sent the last message, no new reply → waiting

Respond with JSON only:
{
  "category": "needs_response|action_required|payment_request|fyi|waiting",
  "confidence": "high|medium|low",
  "reasoning": "brief explanation",
  "detected_language": "cs|en|de|..."
}"""


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
