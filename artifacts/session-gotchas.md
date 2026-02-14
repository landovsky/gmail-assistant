# Session Gotchas & Lessons Learned

Extracted from analysis of 4 major development sessions (1,612 total turns).
Prevents repeating past mistakes during future development.

## Gmail API

- `delete_email` is **permanent and irreversible** — use `modify_email` with `addLabelIds: ["TRASH"]` instead (recoverable 30 days)
- `draft_email` MCP returns a **draft resource ID** (e.g. `r-7936...`), NOT a message ID — search `in:draft <keywords>` to get the actual message ID
- **Gmail label modifications can fail silently** — classification completes in DB but label not applied in Gmail. Must raise/retry on API failures, never swallow errors.
- **Gmail labels are per-message, not per-thread** — searching for unlabeled emails returns other messages from already-processed threads. Always deduplicate by thread ID against DB.

## Async / FastAPI

- **All blocking I/O in async handlers must use `asyncio.to_thread()`** — one sync call (`classify()`, `generate_draft()`, `sync_user()`) blocks the entire FastAPI event loop and freezes the server
- **Job queue race condition**: Never do SELECT-then-UPDATE for concurrent claim operations — use atomic `UPDATE ... RETURNING` (SQLite 3.35+)

## Shell / Bash

- **Shell wrapper scripts need `exec`** — without it, Ctrl+C (SIGINT) goes to the shell parent, not the child process (e.g. uvicorn). Always `exec` the final command.
- **macOS `date` has no `%N` (nanoseconds)** — `date +%s%N` produces garbage. Use `python3 -c "import time; print(time.time())"` or `gdate` from coreutils.
- **Subagent Bash permissions differ from parent** — don't assume subagents can run Bash. Have a fallback.
- **Remote/background sessions require claude.ai auth**, not API Console auth — check auth state before spawning remote work.

## Architecture / Design

- **Always include an audit/event log table from the start** for any system that modifies external state (`email_events` was added after the fact)
- **Keep `🤖 AI/Done` as permanent audit marker** — never remove all labels from processed emails, or you lose traceability in Gmail
- **Inline SQL in markdown prompts is fragile** — LLM can subtly deviate (wrong column, missing `updated_at`). Move SQL into typed repository functions.
- **Default to bounded batch operations** — 30-day lookback for email ingestion, not full mailbox scan. Always define sensible defaults.
- **Design for context from day 1** — drafts without related-thread lookup are shallow. Context gatherer should be a core component.

## Performance

- **Always measure before optimizing** — assumed Gmail searches were 42-85% of processing time; measured only 6%. Real bottleneck was sequential LLM processing at 68% (~33s/email).

## UX / Mobile

- **Design for mobile-first input** — complex markers (`---✂--- Your instructions above this line`) don't work on phones. Use single-tap elements (✂️ emoji).
- **Verify Gmail label structure matches spec** before creating labels — flat vs nested labels caused rework.

## Middleware / Auth

- **Never put handler dispatch inside a broad try/except** — in `BasicAuthMiddleware`, `await self.app(scope, receive, send)` was inside the same `try/except Exception: pass` as base64 decoding. Any handler exception (e.g. `IntegrityError`, `OSError`) was silently caught and fell through to the 401 response, making it look like an auth failure. Fix: parse credentials in the try block, dispatch to handler outside it.
- **K8s Secret volumes are always read-only** — even without `readOnly: true` in the volumeMount. If your app needs to write (e.g. OAuth token refresh writing to `token.json`), use an initContainer to copy from Secret volume to an emptyDir, then mount the emptyDir.
- **Fresh production DB has no users** — `POST /api/sync` with `user_id=1` hits `FOREIGN KEY constraint failed` if no user exists. Must call `POST /api/auth/init` first to bootstrap the first user via OAuth + onboarding.

## Config / Git Hygiene

- **Git-ignore personal config files** — `communication_styles.yml` and `contacts.yml` contain real email addresses. Check in `.example` versions only.
- **MCP tools are visible to ALL commands** — if a tasks MCP is enabled, the model can query it during any command, not just the one that "needs" it.
- **Add a smoke test that imports `src.main`** — catches missing dependencies added by remote PRs that aren't installed locally.

## Process

- **Don't become the tool** — spending 100+ turns manually triaging emails instead of building the automation. Build first, validate with a few examples, then automate.
- **Start from structured data for search** — ad-hoc email exclusions (`-to:foo -subject:bar`) are fragile and change over time. Use `contacts.yml` or DB records for targeted queries.

## Test Gaps Identified

1. **No smoke test importing `src.main`** — missing dependencies go undetected
2. **No test for Gmail label application** — silent failures in label modification
3. **No end-to-end pipeline test** (webhook → sync → classify → draft) — see beads issue `gmail-assistant-zfk`
4. **No test for job queue concurrency** — race conditions in `claim_next`
