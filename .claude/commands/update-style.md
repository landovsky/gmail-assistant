# Update Style

Learn communication patterns from real email history and update the style config.

**Argument:** `$ARGUMENTS` — the style name to update (e.g. `business`, `formal`, `informal`).

**Model:** Use opus for this command (high-quality analysis needed).

## Inputs

- Style config: `config/communication_styles.yml`
- Contacts config: `config/contacts.yml` (for style overrides and domain mappings)
- Style to update: the `$ARGUMENTS` value — must match a key under `styles:` in the YAML

## Validation

1. Read `config/communication_styles.yml` and confirm the requested style exists.
   If it doesn't, list available styles and stop.

## Step 1: Find relevant sent emails (last 60 days)

Use a layered search strategy. Run all searches with `newer_than:60d`.

### Layer 1: Explicit contacts from contacts.yml

Read `config/contacts.yml`. For each email in `style_overrides` mapped to the target
style, search: `in:sent to:<email> newer_than:60d`

### Layer 2: Domain-based search

Identify domains associated with the target style:
- From `style_overrides`: extract unique domains of contacts mapped to this style
- From `domain_overrides`: find domains mapped to this style
- Also include domains that appear related (e.g. if `petr@hristehrou.cz` is business,
  search `in:sent to:hristehrou.cz newer_than:60d` to catch all contacts at that domain)

Search each domain: `in:sent to:<domain> newer_than:60d` with maxResults: 20.

### Layer 3: Broad fallback for unknown contacts

Search for replies not already covered by layers 1-2:
```
in:sent newer_than:60d subject:Re: -to:<domain1> -to:<domain2> ...
```
Exclude domains already searched. Use maxResults: 20.

### Filtering

From the combined results, discard:
- **Automated senders**: where From is not the user (e.g. system notifications
  appearing in sent due to aliases/forwarding)
- **Pure forwards**: subject starting with `Fwd:` — these contain no original
  composition to learn from
- **Automated recipients**: emails to no-reply addresses, notification systems

For the remaining emails, classify each as matching the target style or not based on:
- The recipient's relationship (client, vendor, partner → business; government → formal; friend → informal)
- The tone of the email itself
- The style's `description` field as a heuristic

Aim to collect 20-40 relevant sent messages for the target style.

## Step 2: Read email content

Deduplicate by thread — if multiple messages belong to the same thread, group them.
Prioritize reading threads with multiple messages (richer signal).

For each relevant thread:
- Use `read_email` on the user's sent message(s) — this often includes quoted
  thread history, so one read may reveal the full conversation
- Extract: language used, greeting, sign-off, tone markers, sentence structure,
  length patterns, how the user responds to different types of messages

Read at most 20 emails total (to stay within reasonable bounds). Prefer diversity
of contacts/situations over depth in a single thread.

## Step 3: Analyze patterns

Analyze the collected emails and identify patterns across these dimensions:

**Language patterns:**
- Greeting formulas (how conversations start)
- Sign-off variations (not just the configured one — what's actually used)
- Sentence length and complexity
- Formality level (tykání vs vykání in Czech, contractions in English)
- Common transitional phrases
- How questions are asked vs statements made

**Behavioral patterns:**
- Typical response length (short/medium/long)
- How urgency or deadlines are communicated
- How requests are made (direct vs indirect)
- How disagreement or pushback is expressed
- How appreciation/thanks is expressed
- Whether emoji are used and which ones

**Structural patterns:**
- Single paragraph vs multi-paragraph
- Use of bullet points or numbered lists
- Whether specific details (dates, amounts, names) are referenced
- Position of the main ask (beginning vs end)

## Step 4: Update the style config

Read the current `config/communication_styles.yml` and update ONLY the target style section:

1. **Update `rules`**: Refine existing rules and add new ones based on observed patterns.
   Keep rules actionable and specific. Remove rules that contradict observed behavior.

2. **Update `examples`**: Replace or add examples using real patterns observed.
   - Use realistic but anonymized scenarios (change names, subjects, amounts)
   - Each example should demonstrate a distinct pattern (don't repeat similar cases)
   - Include 2-4 examples total
   - Examples should reflect the actual tone and structure found in real emails

3. **Update `sign_off`** if the observed sign-off differs from the configured one.

4. **Update `language`** if the observed pattern differs.

5. Do NOT modify other styles. Do NOT change the `default` setting.

Write the updated YAML back using the Edit tool.

## Step 5: Summary

Print a clear summary of what changed:

```
## Style updated: business

### Emails analyzed
- 18 sent emails from last 60 days
- Contacts: petr@hristehrou.cz (7), client@example.com (5), vendor@co.cz (6)

### Changes made
- Rules: added 3, modified 1, removed 0
  - Added: "Use single-paragraph responses for simple confirmations"
  - Added: "Lead with the answer/decision, then provide context"
  - Added: "Reference previous thread context briefly rather than restating"
  - Modified: sign_off from "Díky, Tomáš" → "Díky, T."
- Examples: replaced 2, added 1
- Sign-off: updated

### Review
Changes written to config/communication_styles.yml — please review and commit.
```

## Important

- This is a learning/analysis tool — it does NOT send or draft any emails.
- Anonymize all example content (change names, companies, amounts, dates).
- Preserve the YAML structure and formatting carefully.
- If fewer than 5 relevant emails are found, warn that the sample size is small
  and the results may not be representative.
- Do not invent patterns — only document what's actually observed in the emails.
