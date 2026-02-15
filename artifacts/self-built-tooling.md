## Self-Built Tooling

You are encouraged to build tools that accelerate your own workflow — but **building the product always comes first**.

### When to Build a Tool

Apply the **Rule of Three**: only build a tool when the same manual task has been done **three times** and is expected to recur. This count is **cumulative across sessions** — check `artifacts/tool-suggestions.md` for prior tallies before deciding.

Before building, briefly justify it:

```
I've done [X] three times now (tallies: [references]). A [script/command/hook] would save ~[Y] minutes
per occurrence. Building it will take ~[Z] minutes. Worth it: [yes/no].
```

If the build cost exceeds the savings over the next ~10 occurrences, skip it.

### Tracking Tool Suggestions

Maintain `artifacts/tool-suggestions.md` to track emerging patterns that haven't yet hit the Rule of Three threshold. **Every time you do a manual task that feels repetitive**, add or update an entry:

```markdown
## [short description of the repetitive task]

- **Tally:** 2
- **Occurrences:**
  - [date] — [bead id]: [brief context of what you were doing]
  - [date] — [bead id]: [brief context]
- **Potential tool:** [what you'd build — script, command, hook, generator]
- **Estimated build time:** [minutes]
- **Status:** watching | **ready to build** | built → [link to artifacts/tools.md entry]
```

Rules:
- **Tally 1:** Log it. Move on.
- **Tally 2:** Update the entry. Move on.
- **Tally 3:** Mark as **ready to build**. You may now build it (subject to the budget limits below).
- When a suggestion is built, update its status to `built` and link to the corresponding `artifacts/tools.md` entry.

Always check this file at the **start of a session**. If a suggestion is already at "ready to build," you can build it as your first task — it counts against your tooling budget.

### What You Can Build

- **Bash scripts** — automating repetitive shell sequences (e.g., bead + branch + commit workflows).
- **Claude Code slash commands** — custom commands in `.claude/commands/` for project-specific workflows.
- **Git hooks** — pre-commit, pre-push checks beyond what the linter covers.
- **Makefile / Taskfile targets** — composite commands for common workflows.
- **Code generators / templates** — when the framework's built-in generators don't cover a recurring pattern in this project.

### Naming Convention

All AI-generated tooling must use the `_agen` suffix (before the file extension) so humans can instantly identify its origin:

- `scripts/sync_beads_agen.sh`
- `.claude/commands/new_feature_agen.md`
- `lib/generators/service_agen.rb`
- `Makefile` targets: `setup-agen`, `workflow-start-agen`
- Git hooks: `pre-commit-agen`

If a human later adopts and modifies the tool, they can remove the suffix to claim ownership.

### Budget

Tooling is tracked as beads like any other work, tagged `[tooling]` in the bead description. Self-imposed limits:

- **No more than 1 tool per 5 feature tasks.** If you've built a tool, ship at least 5 product beads before building another.
- **No tool may take longer than 15 minutes to build and test.** If it's more complex, create a bead for it and let a human decide whether to prioritize it.
- **No speculative tooling.** Only build what solves a problem you've already hit, not one you might hit later.

### Storage

Keep all self-built tooling organized:

```
scripts/          # Bash scripts
.claude/commands/ # Claude Code slash commands
```

Add a one-liner for each tool in `CLAUDE.md` under an `## Agent Tooling` section so future sessions know what's available.

### Documentation

Maintain `artifacts/tools.md` as the detailed registry of all agent-built tooling. For every tool you create, add an entry:

```markdown
## [tool name]

- **File:** `path/to/tool_agen.sh`
- **Created:** [date]
- **Bead:** [bead id]
- **Purpose:** [what problem it solves]
- **Trigger:** [what repetitive task prompted its creation — the "Rule of Three" justification]
- **Usage:** `[example invocation]`
- **Dependencies:** [any tools, packages, or environment requirements]
- **Notes:** [quirks, limitations, known issues, or context that isn't obvious from the code]
```

When you modify an existing tool, update its entry and add a changelog line:

```markdown
- **Changelog:**
  - [date]: [what changed and why]
```

This file is the source of truth for understanding **why** each tool exists. The code shows *what* it does; `artifacts/tools.md` shows *why* it was built and *when* to reach for it.
