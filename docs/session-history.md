# Claude Code Session History

> **Access any session**: `claude --resume <session-id>`
> Sessions are stored in `~/.claude/projects/-Users-tomas-git-ai-gmail-assistant/<id>.jsonl`

## Development Sessions (sorted by total turns)

| # | Status | Turns | Size | Last Active | Session ID | Summary |
|---|--------|-------|------|-------------|------------|---------|
| 1 | done | 794 | 3.4M | Feb 12 14:16 | `4b97e517-6601-4bac-9679-626c372dfc1f` | Review spec, prepare for implementation |
| 2 | done | 408 | 2.3M | Feb 13 16:37 | `64138000-abe8-4f06-b368-71b2ccd82bd2` | Orchestration session (local-command) |
| 3 | | 397 | 1.8M | Feb 13 10:28 | `103529f1-26c3-44b8-a7ee-efa73cf20ebf` | Orchestration session (local-command) |
| 4 | | 345 | 2.5M | Feb 13 18:06 | `d22335ce-7578-4975-b7b8-a987cb801600` | Orchestration session (local-command) |
| 5 | | 328 | 1.1M | Feb 12 15:11 | `39b0e51d-a482-4d25-a408-35fb939db213` | Orchestration session (local-command) |
| 6 | | 313 | 1.5M | Feb 12 16:50 | `5c6fd970-08af-45de-b4a3-0e54abfb73bf` | Orchestration session (local-command) |
| 7 | | 299 | 944K | Feb 13 18:29 | `6a8c42b5-2f29-419d-bb3c-7aab2e30664d` | Orchestration session (local-command) |
| 8 | done | 241 | 798K | Feb 12 15:26 | `fd7c244c-1c6d-4cdb-b46a-5bf79142ac66` | Create cleanup claude command |
| 9 | | 201 | 477K | Feb 13 10:47 | `5a975115-a404-43f5-b1af-cf33f46c25d9` | (interrupted by user) |
| 10 | | 198 | 675K | Feb 13 17:08 | `a139763b-4005-46c2-b60d-bce0b686f565` | Orchestration session (local-command) |
| 11 | done | 169 | 1.7M | Feb 12 18:36 | `bf9b4dac-16b2-4fce-a12d-24cb2c25fab0` | DB API vs raw SQL discussion + refactor |
| 12 | | 152 | 571K | Feb 12 17:10 | `95b6e0cf-b457-4d77-ab76-0854bb55d6f4` | (interrupted by user) |
| 13 | | 133 | 1.1M | Feb 13 10:30 | `7f832425-ee58-4b40-b8cf-3396b63b6c52` | /claude-project-setup for hriste |
| 14 | | 99 | 362K | Feb 12 16:22 | `0341faaa-3be7-41ac-8225-c6f4f0e2d479` | Verify bd sync setup for remote branch |
| 15 | | 88 | 752K | Feb 13 16:13 | `10b442d7-fdf5-4b68-82d3-d01cedcf3211` | Create /send-test-email command |
| 16 | | 77 | 217K | Feb 13 17:01 | `6ddeb5e3-f52e-4d25-b96f-4b02ef9641f7` | Fix test-classification traceback |
| 17 | | 64 | 955K | Feb 13 16:51 | `ab72116e-2461-4523-9472-38c3a33e827e` | Review classification testing system |
| 18 | | 58 | 143K | Feb 13 17:52 | `f5cb9ed2-fbaf-43a5-8ede-401585fce08f` | LiteLLM config fix (anthropic dependency) |
| 19 | | 58 | 118K | Feb 12 13:11 | `cc449b2f-9226-4179-8cd0-836a6537840e` | Init beads + git setup |
| 20 | | 17 | 315K | Feb 12 14:15 | `9a9ca20a-efa9-4632-9113-ef5bb3caa3c9` | Multi-tenancy design discussion |

## Automated Skill Sessions (60+ sessions)

Inbox Triage, Cleanup, Draft Response, Process Invoices, Rework Draft, Morning Briefing, Send Test Email runs. These are routine operations, not development. Skipped for analysis.

---

## Extracted Gotchas & Lessons

### Session 1: Review spec + implementation (794 turns) `4b97e517`

| # | Category | Finding | Lesson |
|---|----------|---------|--------|
| 1.1 | gotcha | `delete_email` is permanent and irreversible. Permission was denied, blocking rework flow. | Use `modify_email` with `addLabelIds: ["TRASH"]` instead. Trash auto-purges in 30 days. |
| 1.2 | user-correction | Draft marker `---✂--- Your instructions above this line / Draft below ---✂---` was too complex for mobile editing. | Simplified to single `✂️` emoji on its own line with 2 blank lines above. Design for mobile-first input. |
| 1.3 | user-correction | Labels were created flat instead of nested under `🤖 AI/`. User had to manually create root label and request nesting. | Always verify Gmail label structure matches spec before proceeding. |
| 1.4 | deficiency | Done cleanup removed ALL `🤖 AI/*` labels, leaving no trace in Gmail of system-processed emails. | Keep `🤖 AI/Done` as permanent audit marker. Never remove all evidence of processing. |
| 1.5 | deficiency | No audit trail for system actions. Had to add `email_events` table after the fact. | Always include an audit/event log table from the start for any system that modifies external state. |
| 1.6 | gotcha | Triage returned duplicate results — Gmail labels are per-message, so other messages in same thread appeared as "unlabeled". | Deduplicate by thread ID against DB when searching for unprocessed emails. |
| 1.7 | deficiency | Assistant spent 100+ turns manually triaging emails instead of building automation. User had to intervene: "I got carried away being the system instead of building it." | When building a tool, don't become the tool. Build first, validate with a few examples, then automate. |
| 1.8 | deficiency | No default scope for email ingestion — would scan entire mailbox on new install. | Default to 30-day lookback with optional override. Always define sensible defaults for batch operations. |
| 1.9 | gotcha | `draft_email` MCP returns a draft resource ID (e.g. `r-7936...`), NOT a message ID. Can't use it with `modify_email` directly. | To find/modify a draft, search `in:draft <keywords>` to get the actual message ID. |

### Session 2: Orchestration — workers, context, sentry (408 turns) `64138000`

| # | Category | Finding | Lesson |
|---|----------|---------|--------|
| 2.1 | gotcha | **Race condition in `claim_next`**: SELECT then UPDATE as separate calls — two workers could claim the same job. | Use atomic `UPDATE ... RETURNING` (SQLite 3.35+) for claim operations. Never do SELECT-then-UPDATE for concurrent job queues. |
| 2.2 | deficiency | **All I/O was synchronous blocking the event loop.** `classify()`, `generate_draft()`, `sync_user()` were regular `def` called from `async def` handlers, blocking the entire server. | Wrap all blocking calls in `asyncio.to_thread()`. FastAPI + async requires discipline — one blocking call freezes everything. |
| 2.3 | bash-issue | **`bin/dev` not cancellable with Ctrl+C.** Plain shell script without `exec`, so SIGINT went to the shell parent, not uvicorn. | Always use `exec` in wrapper scripts to replace the shell process. Add shebangs. |
| 2.4 | test-gap | **`sentry-sdk` import error at startup.** Package added by remote Claude in a PR but not installed in local venv. No test caught it because no test imports `src.main`. | Add a smoke test that imports the app entrypoint (`from src.main import app`). Tests should cover import chains. |
| 2.5 | gotcha | **Gmail label modification failed silently.** Classification completed (DB + event logged) but Gmail API label call failed with no error surfaced. Email appeared unclassified to user. | Gmail API failures must be loud — raise/retry, don't swallow. Test that label application actually reaches Gmail (or mock asserts it). |
| 2.6 | deficiency | **No context for draft generation.** System only saw current thread (3000 chars). Prior conversations with same person/topic were invisible, producing shallow responses. | Built context gatherer: Gmail search for related threads by sender + subject keywords. Design for context from day 1. |
| 2.7 | gotcha | **Style system existed but was disconnected.** v1 had 3 writing styles (business, personal, formal) with domain overrides in `contacts.yml`, but the resolution chain wasn't obvious. | Document style resolution priority: exact email > domain glob > default. Ensure config is tested. |

### Session 8: Create cleanup + update-style command (241 turns) `fd7c244c`

| # | Category | Finding | Lesson |
|---|----------|---------|--------|
| 8.1 | deficiency | **Ad-hoc email search for style learning was manual and fragile.** Initial approach used broad `in:sent newer_than:60d` with iterative exclusions — noise sources change over time, won't work as reusable command. | Start from `contacts.yml` for targeted per-domain searches, then broad fallback. Data-driven search beats ad-hoc exclusions. |
| 8.2 | gotcha | **Config files with personal data were committed to git.** `communication_styles.yml` and `contacts.yml` contain real email addresses, domains, personal preferences. | Git-ignore personal config files, check in `.example` versions. Keep originals locally only. |
| 8.3 | gotcha | **MCP tools are visible to ALL commands.** If a tasks MCP (Linear, Jira) is enabled, the model drafting responses can opportunistically query it — useful but not guaranteed. | Be aware that MCP tools "leak" across commands. Design prompts knowing the model sees all available tools. |

### Session 11: DB API refactor + performance analysis (169 turns) `bf9b4dac`

| # | Category | Finding | Lesson |
|---|----------|---------|--------|
| 11.1 | gotcha | **Performance analysis was wrong about the bottleneck.** Assumed Gmail searches took 42-85% of time (250-500s). Measured: Gmail searches were only 6% (36s). Real bottleneck was **sequential LLM processing at 68% (~400s, ~33s/email).** | Always measure before optimizing. Intuition about bottlenecks is often wrong. Profile first. |
| 11.2 | bash-issue | **macOS `date` doesn't support `%N` (nanoseconds).** Timing scripts using `date +%s%N` produced garbage output with literal "N" suffix. | Use `python3 -c "import time; print(time.time())"` for sub-second timing on macOS, or `gdate` from coreutils. |
| 11.3 | bash-issue | **Subagent Bash permissions differ from parent.** Batch-labels perf test subagent couldn't run Bash — had to fall back to running it in the parent session. | Don't assume subagents have identical tool permissions. Have fallback for permission-denied scenarios. |
| 11.4 | bash-issue | **Background task creation failed: Console vs claude.ai auth mismatch.** `Failed to create remote session` error required `/login` with claude.ai account, not Console. Repeated failures before resolution. | Remote/background sessions require claude.ai auth, not API Console auth. Check auth state before spawning remote work. |
| 11.5 | deficiency | **Inline SQL in markdown prompts is fragile.** ~21 SQL operations lived as inline commands in prompt files. LLM interprets and fills values at runtime — can subtly deviate (wrong column, missing `updated_at`). | API/repository layer provides correctness guarantees. Move SQL out of prompts into typed Python functions. |

