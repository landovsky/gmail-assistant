"""Draft generation prompt templates — ported from .claude/commands/draft-response.md."""


def build_draft_system_prompt(
    style_config: dict,
    resolved_style: str,
) -> str:
    """Build the system prompt for draft generation."""
    style = style_config.get("styles", {}).get(resolved_style, {})
    rules = style.get("rules", [])
    sign_off = style.get("sign_off", "")
    language = style.get("language", "auto")
    examples = style.get("examples", [])

    rules_text = "\n".join(f"- {r}" for r in rules)

    examples_text = ""
    for ex in examples:
        examples_text += f"\nContext: {ex.get('context', '')}\n"
        examples_text += f"Input: {ex.get('input', '')}\n"
        examples_text += f"Draft:\n{ex.get('draft', '')}\n"

    return f"""You are an email draft generator. Write a reply following the communication style rules below.

Style: {resolved_style}
Language: {language} (if "auto", match the language of the incoming email)

Rules:
{rules_text}

Sign-off: {sign_off}

{f'Examples:{examples_text}' if examples_text else ''}

Guidelines:
- Match the language of the incoming email unless the style specifies otherwise.
- Keep drafts concise — match the length and energy of the sender.
- Include specific details from the original email (dates, names, numbers).
- Never fabricate information. If context is missing, flag it with [TODO: ...].
- Use the sign_off from the style config.
- Do NOT include the subject line in the body.
- Output ONLY the draft text, nothing else."""


def build_draft_user_message(
    sender_email: str,
    sender_name: str,
    subject: str,
    thread_body: str,
    user_instructions: str | None = None,
    related_context: str | None = None,
) -> str:
    """Build the user message for draft generation."""
    parts = [
        f"From: {sender_name} <{sender_email}>" if sender_name else f"From: {sender_email}",
        f"Subject: {subject}",
        "",
        "Thread:",
        thread_body[:3000],
    ]

    if related_context:
        parts.extend(["", related_context])

    if user_instructions:
        parts.extend([
            "",
            "--- User instructions ---",
            user_instructions,
            "--- End instructions ---",
            "",
            "Incorporate these instructions into the draft. They guide WHAT to say, "
            "not HOW to say it. The draft should still follow the style rules.",
        ])

    return "\n".join(parts)


def build_rework_user_message(
    sender_email: str,
    sender_name: str,
    subject: str,
    thread_body: str,
    current_draft: str,
    rework_instruction: str,
    rework_count: int,
) -> str:
    """Build the user message for rework draft generation."""
    parts = [
        f"From: {sender_name} <{sender_email}>" if sender_name else f"From: {sender_email}",
        f"Subject: {subject}",
        f"Rework #{rework_count + 1}",
        "",
        "Thread:",
        thread_body[:3000],
        "",
        "Current draft:",
        current_draft,
        "",
        "User feedback / instructions:",
        rework_instruction,
        "",
        "Regenerate the draft incorporating the user's feedback. "
        "Preserve any factual content the user added. "
        "If the instruction is ambiguous, err on the side of minimal changes.",
    ]

    return "\n".join(parts)


# Rework marker
REWORK_MARKER = "✂️"


def wrap_draft_with_marker(draft_body: str) -> str:
    """Prepend the rework marker to a draft body."""
    return f"\n\n{REWORK_MARKER}\n\n{draft_body}"


def extract_rework_instruction(draft_body: str) -> tuple[str, str]:
    """Extract user instructions (above marker) and draft (below marker).

    Returns (instruction, draft_below_marker).
    """
    if REWORK_MARKER not in draft_body:
        return "", draft_body

    parts = draft_body.split(REWORK_MARKER, 1)
    instruction = parts[0].strip()
    draft = parts[1].strip() if len(parts) > 1 else ""
    return instruction, draft
