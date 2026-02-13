# Code Review

Run a full codebase review for anti-patterns, non-Pythonic idioms, and emerging architectural cracks. Triage findings and commit as an artifact.

**Argument:** `$ARGUMENTS` — optional focus area (e.g. `db`, `async`, `workers`, `api`). If omitted, review the entire `src/` tree.

## Context

- Previous review: `artifacts/codebase-review-antipatterns.md` — read this first to understand what has already been flagged and avoid duplicating resolved items.
- Architecture docs: check `artifacts/` for project overview, conventions, and domain docs.
- Schema: `src/db/migrations/` for current table definitions.

## Step 1: Scope

If `$ARGUMENTS` specifies a focus area, limit the review to matching modules:
- `db` → `src/db/`, schema, repository pattern
- `async` → async/sync boundaries, `asyncio.to_thread` usage, event loop blocking
- `workers` → `src/tasks/`, job dispatch, handler logic
- `api` → `src/api/`, route definitions, request handling
- `gmail` → `src/gmail/`, API client, models, auth
- `classify` → `src/classify/`, rules, prompts, engine
- `draft` → `src/draft/`, prompts, engine
- `sync` → `src/sync/`, history processing, webhook, watch
- `lifecycle` → `src/lifecycle/`, state machine transitions
- `config` → `src/config.py`, `src/users/settings.py`, YAML loading

If no argument, review all of `src/`.

## Step 2: Read code

Read every Python file in the scoped modules. Do not skip files — thoroughness matters more than speed. For each file, look for:

### Anti-patterns
- God Objects (classes doing too many things)
- Copy-pasted logic that should be factored out
- Mutable default arguments
- Bare `except Exception` that swallows errors silently
- String-typed values that should be enums
- SQL injection vectors (string formatting in queries)
- Inconsistent error handling (some paths return None, others raise)

### Non-Pythonic code
- Manual loops where comprehensions, `itertools`, or builtins would be clearer
- `if x == True` / `if x == None` instead of `if x` / `if x is None`
- Not using context managers for resource management
- Reimplementing stdlib functionality (email parsing, path handling, etc.)
- Type annotations that are too loose (`Any` where a concrete type is known)
- Imports in wrong order or location

### Architectural cracks
- Coupling between modules that should be independent
- Inconsistent patterns across similar code (e.g. some repos return dicts, others dataclasses)
- Missing abstractions that would prevent copy-paste
- Boundary violations (business logic in API routes, DB concerns in domain code)
- State management issues (globals, singletons, hidden dependencies)
- Sync/async boundary inconsistencies

## Step 3: Cross-reference with previous review

Read `artifacts/codebase-review-antipatterns.md`. For each previously flagged issue:
- If **fixed**: note it as resolved
- If **still present**: keep it (update description if the code changed)
- If **partially addressed**: note what remains

Remove resolved items. Add new findings.

## Step 4: Triage

Assign each finding a severity:

| Severity | Meaning |
|----------|---------|
| **P0 — fix now** | Will cause bugs or data loss under normal operation |
| **P1 — fix soon** | Correctness risk under concurrency or growth; tech debt that compounds |
| **P2 — plan for** | Design friction that slows future work; non-Pythonic idioms |
| **P3 — consider** | Minor style or ergonomic nits |

For each finding, include:
- **File and line reference** (e.g. `src/db/connection.py:65`)
- **Code snippet** showing the problem
- **Why it matters** — concrete consequence, not abstract principle
- **Suggested fix** — brief, actionable

## Step 5: Write the document

Update `artifacts/codebase-review-antipatterns.md` with the triaged findings. Preserve the existing structure:

```markdown
# Codebase Review: Anti-patterns, Non-Pythonic Code, and Architectural Cracks

**Date:** <today>
**Scope:** <what was reviewed>

---

## Triage Legend
...

## P0 — Fix Now
### 1. Title
**Files:** ...
<description with code snippets>
**Fix:** ...

## P1 — Fix Soon
...

## P2 — Plan For
...

## P3 — Consider
...

## Architectural Cracks — Summary
<narrative section on the 3-5 biggest structural concerns>
```

## Step 6: Commit

Commit the updated artifact with a message describing what changed:
- How many issues found/resolved/remaining per severity
- Which modules were reviewed

## Important

- Read actual code — do not guess or assume. Every finding must reference a specific file and line.
- Be concrete, not vague. "Error handling is inconsistent" is not useful. "get_message returns None on error but create_draft raises RuntimeError" is useful.
- Don't flag things that are intentional trade-offs documented in CLAUDE.md or artifacts.
- Don't suggest adding docstrings, comments, or type annotations to code you didn't review for functional issues.
- Focus on things that will cause bugs, slow development, or make the codebase harder to maintain.
