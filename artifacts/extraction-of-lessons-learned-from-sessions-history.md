# Extraction of Lessons Learned from Session History

## Motivation

After several intensive development sessions building gmail-assistant v2, we accumulated 127 Claude Code sessions totaling thousands of turns across 2 days. Mistakes were made, corrected, and learned from — but those lessons lived only in ephemeral session transcripts stored in `~/.claude/projects/`. These files are not committed to git, not shared across machines, and will eventually be lost to disk cleanup or machine migration.

This effort extracts **actionable gotchas** from past sessions so that future development (by human or AI) avoids repeating the same mistakes. The output is `artifacts/session-gotchas.md`, registered with `usage: "always"` so Claude ingests it at every session start.

## Outputs

| File | Purpose |
|------|---------|
| `artifacts/session-gotchas.md` | Consolidated findings, grouped by topic. Loaded by Claude automatically. |
| `docs/session-history.md` | Session index with IDs, turn counts, summaries. Tracks which sessions have been analyzed. |
| `bin/extract-session-messages` | Script to extract user + assistant messages from a session JSONL. |
| `bin/list-sessions` | Script to list all sessions for this project with metadata. |

## Method

### Step 1: List all sessions

Session data lives in `~/.claude/projects/-Users-tomas-git-ai-gmail-assistant/*.jsonl`. Each file is a newline-delimited JSON log of one Claude Code session. The format has these message types:

- `file-history-snapshot` — file state snapshots (bulk of the file, skip these)
- `user` — human messages (wrapped in system-reminder tags that must be stripped)
- `assistant` — Claude responses (can be string or content-block array)
- `progress` — tool execution progress
- `system` — system messages
- `queue-operation` — internal scheduling

We parse each file, count user/assistant turns, extract the first meaningful user message as a summary, and sort by total turns descending. See `bin/list-sessions`.

### Step 2: Triage sessions

From 127 sessions, we identified:
- **20 development sessions** (interactive work with human guidance)
- **60+ automated skill runs** (routine `/inbox-triage`, `/cleanup`, `/draft-response` executions — low lesson density)
- **7 orchestration sessions** (local-command dispatchers — mostly coordination, not where mistakes happen)

Prioritized by turn count: more turns = more work = more potential mistakes.

### Step 3: Extract findings per session

For each session, run `bin/extract-session-messages` which:
1. Reads the JSONL file
2. Extracts all user messages (stripping `<system-reminder>`, `<command-*>` tags)
3. Extracts assistant messages containing error/fix keywords: `error`, `fix`, `wrong`, `failed`, `traceback`, `issue`, `retry`, `workaround`, `actually`, `instead`, `broke`
4. Outputs both sets for human review

The human (or Claude) then reviews the output and identifies:
- **gotcha** — unexpected behavior that caused wasted effort
- **deficiency** — missing capability that had to be added retroactively
- **user-correction** — human had to step in and redirect
- **bash-issue** — shell/tooling problems
- **test-gap** — missing test that would have prevented an error

### Step 4: Consolidate and save

Findings written to `artifacts/session-gotchas.md`, grouped by topic (Gmail API, async, shell, architecture, performance, UX, config, process, test gaps). Registered in `artifacts/registry.json` with `usage: "always"`.

Per-session detail kept in `docs/session-history.md` tables for traceability.

## What was processed

| Session | Turns | Topic | Findings |
|---------|-------|-------|----------|
| #1 `4b97e517` | 794 | Review spec + implementation | 9 (draft deletion, mobile UX, labels, audit trail, dedup, scope) |
| #2 `64138000` | 408 | Workers, context, sentry | 7 (race condition, async blocking, Ctrl+C, silent Gmail failures) |
| #8 `fd7c244c` | 241 | Cleanup command, style learning | 3 (ad-hoc search, personal config in git, MCP leaking) |
| #11 `bf9b4dac` | 169 | DB API refactor + performance | 5 (wrong bottleneck, macOS date, subagent perms, auth mismatch) |
| **Total** | **1,612** | | **24 findings** |

## Observations

- **Sessions 1 and 2 had the richest material.** Foundational implementation sessions surface the most gotchas because that's where architectural decisions are made and wrong assumptions hit reality.
- **Diminishing returns after session 2.** Later sessions produced fewer novel findings — many were variations of patterns already captured.
- **Orchestration sessions are low-yield.** Sessions 3-7 (local-command dispatchers) are mostly routing work to sub-sessions. The actual mistakes happened in the child sessions.
- **Automated skill runs are not worth analyzing for gotchas.** They execute a fixed prompt against real data — failures there are operational (wrong classification, bad draft) not developmental.

## Scripts

### `bin/list-sessions`

Lists all Claude Code sessions for this project with turn counts, sizes, and first user message.

```bash
bin/list-sessions                # all sessions, sorted by turns
bin/list-sessions --dev-only     # skip automated runs (< 7 turns)
bin/list-sessions --min-turns 50 # only substantial sessions
bin/list-sessions --json         # machine-readable output
```

### `bin/extract-session-messages`

Extracts user messages and error-indicator assistant messages from a single session. Supports partial session ID matching.

```bash
bin/extract-session-messages 4b97e517                # error/fix messages (default)
bin/extract-session-messages 4b97e517 --all          # all assistant messages
bin/extract-session-messages 4b97e517 --user-only    # only user messages
bin/extract-session-messages 4b97e517 --max-len 300  # truncate at 300 chars
```

The error filter looks for keywords: `error`, `fix`, `wrong`, `failed`, `traceback`, `issue`, `retry`, `workaround`, `actually`, `instead`, `broke`, etc.

## Picking this up later

To continue analyzing remaining sessions:

1. Check `docs/session-history.md` — unprocessed sessions have empty Status column
2. **Priority targets**: #16 (fix test-classification, 77 turns), #18 (LiteLLM config, 58 turns) — small, focused, likely have concrete bugs
3. **Skip**: orchestration sessions (#3-7, #9-10) — low-yield coordination logs
4. Run `bin/extract-session-messages <session-id>` to get raw material
5. Review output, identify patterns, add to `artifacts/session-gotchas.md`
6. Mark session as `done` in `docs/session-history.md` table
