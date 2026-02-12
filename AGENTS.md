# Agent Instructions

## Project Overview

**Gmail Inbox Management System** is a self-hosted system that processes Gmail via MCP, classifies emails, generates draft responses, and surfaces actions through Gmail labels (mobile) and a local HTML dashboard (desktop). The processing pipeline runs as Claude Code custom commands using cost-appropriate models.

## Task Management

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

### Workflow

1. Check `bd ready` for available issues (no blockers)
2. Claim with `bd update <id> --status in_progress`
3. Complete work and commit changes
4. Close with `bd close <id> --reason="description"`
5. Run `bd sync` before ending session

## Artifacts Registry

This project maintains a registry of documentation artifacts at **`artifacts/registry.json`**.

### How to Use the Registry

1. **Read `artifacts/registry.json`** at the start of every task
2. **Read all `"usage": "always"` artifacts** immediately - these contain core project conventions
3. **Scan `"usage": "decide"` artifacts** by their `description` field - read any that are relevant to your current task
4. **Follow the conventions** documented in artifacts when writing or modifying code

### When to Consult the Registry

- Starting work on a new feature or bug fix
- Working with unfamiliar parts of the codebase
- Writing or modifying tests
- Making architectural decisions

### Registry Structure

Each artifact entry contains:
```json
{
  "filename": "path/to/artifact.md",
  "description": "Brief description of what the artifact covers",
  "usage": "always" | "decide"
}
```

**Usage field:**
- **`always`** - Must be read before any work (e.g., project overview, core conventions)
- **`decide`** - Read when the artifact is relevant to your current task

### Maintaining the Registry

When you create new documentation or discover patterns worth preserving:

1. Write the artifact to `artifacts/` (or appropriate location)
2. Add an entry to `artifacts/registry.json` with a descriptive `description` and correct `usage` level
3. Keep descriptions concise but specific enough for agents to decide relevance from the description alone

## Project Structure

```
gmail-assistant/
├── docs/                            # Specifications and design docs
│   └── gmail-inbox-manager-spec.md  # Main system specification
├── artifacts/                       # Documentation artifacts
├── .mcp.json                        # MCP server configuration (Gmail)
└── AGENTS.md                        # This file
```

## Development Guidelines

### Code Style

- Follow existing patterns in the codebase
- Keep components focused and single-purpose
- Document complex logic with comments

### Git Workflow

1. Work on feature branches
2. Commit frequently with descriptive messages
3. Use conventional commit format: `feat:`, `fix:`, `chore:`, etc.
4. Add `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` to commit messages
5. Run `bd sync` to sync beads with git
6. Push to remote regularly

## Session Close Checklist

Before saying "done" or "complete":

```
[ ] git status              # Check what changed
[ ] git add <files>         # Stage code changes
[ ] bd sync                 # Commit beads changes
[ ] git commit -m "..."     # Commit code with Co-Authored-By
[ ] bd sync                 # Commit any new beads changes
[ ] git push                # Push to remote
```

**Never skip this.** Work is not done until pushed.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
