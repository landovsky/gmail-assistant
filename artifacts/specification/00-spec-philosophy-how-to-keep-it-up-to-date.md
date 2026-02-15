# Spec Philosophy & Maintenance

## What this is

A technology-agnostic behavioral specification of a production system — what it does, not how it's built. A senior developer with no prior context should be able to rebuild the system on any suitable stack producing functionally identical results.

## Core principles

**Behavior over implementation.** Describe what happens, not which framework method to call. "Return 404 when the resource doesn't exist" — not "use `find_by!` with a rescue."

**Mirror, not roadmap.** The spec reflects current production behavior. Nothing aspirational, no TODOs. If it's not shipped, it's not in the spec.

**One canonical definition.** Every entity, rule, or contract is defined in exactly one place. Other documents reference it, never redefine it.

**Honest about ambiguity.** When behavior couldn't be fully determined from code analysis, it's marked `[UNCLEAR: description]`. These are decision points for the rebuilder — resolve them, don't delete them silently. When you resolve one, replace it with the determined behavior and leave a note:

```markdown
<!-- Before -->
[UNCLEAR: Whether expired invitations are hard-deleted or soft-deleted on cleanup]

<!-- After -->
Expired invitations are soft-deleted (marked with `deleted_at` timestamp) and
permanently purged after 90 days by the `PurgeExpiredInvitations` job.
<!-- Resolved 2026-02-14: confirmed via production DB — soft delete with
deleted_at column exists on invitations table -->
```

**Precision is the standard.** Spec documents are behavioral contracts, not approximations. If the spec says `404` with body `{ "error": "not_found", "message": "..." }`, the rebuild must return exactly that — not `200` with an empty body, not a different error shape. This applies everywhere: status codes, error formats, validation rules, side effects. Read every statement as a constraint on the rebuild.

**Every interface is a first-class deliverable.** The system communicates through multiple interface types — Web UI, REST API, CLI tools, webhooks, background jobs, pub/sub, etc. Each one must be fully specified. No interface should be reduced to an afterthought or left as "just endpoints." Specifically:

- **Web UI** — Describe as a real, rendered interface: what it displays, what can be searched/filtered/sorted, what actions it supports, navigation structure. Do not reduce to a list of JSON endpoints.
- **REST API** — Routes, request/response shapes, auth, pagination, error handling, status codes, edge cases.
- **CLI / operational tooling** — Describe *purpose*, *inputs*, and *expected behavior/output*. Do not prescribe flag names, argument syntax, or invocation style — the rebuilder will implement idiomatically for their stack.
- **Webhooks, workers, pub/sub** — Payload formats, triggers, retry behavior, failure modes, side effects.

**No stack leakage.** The spec must not constrain the rebuilder's technology choices. No framework DSLs, no ORM syntax, no CLI argument formats. A Rails rebuild uses rake tasks; a Node project uses npm scripts; a Python project uses management commands — the spec should work for all of them.

## Keeping it current

**Spec changes ship with code changes.** No behavior change is done until the spec reflects it. Same PR, same branch.

**Re-generate to audit.** Periodically re-run the generation prompt against the codebase and diff the output against the maintained spec. This catches drift, missing coverage, and stale descriptions. Use these prompt patterns:

*Targeted update (single feature changed):*
> I changed [specific behavior]. Here is the diff: [paste diff].
> Update [specific spec document] to reflect this change.
> Do not modify anything unaffected. If the change affects test cases, update those too.

*Periodic audit (quarterly or post-refactor):*
> Here is the maintained spec: [documents].
> Here is a freshly generated spec from the current codebase: [documents].
> Identify: (1) contradictions, (2) behavior in fresh but missing from maintained,
> (3) behavior in maintained but missing from fresh.
> Do not resolve — just list discrepancies for human review.

**Test cases are contracts.** The integration/acceptance test cases define the behavioral surface. When behavior changes, check whether test cases need updating too.

## Generation prompt

Preserved here for re-generation and audits. Feed it to an agent alongside the codebase.

> Analyze this system and produce a technology-agnostic specification that could be used to rebuild it from scratch on any suitable stack (e.g., Rails, NestJS, Express, Django).
>
> **Structure:** Up to 12 self-referential documents. Choose a structure that makes sense for the system's complexity (e.g., data model, API contracts, background jobs, integrations, business logic/domains).
>
> **Interfaces — identify all of them:** Inventory every interface the system exposes or consumes. Each is a first-class deliverable. Common types: Web UI (real rendered interface, not JSON endpoints), REST API, CLI tools (purpose/inputs/behavior, not flag syntax), webhooks, background workers, pub/sub. If the system has others, document them with the same rigor.
>
> **Include:** Data model with relationships/validations/invariants · All interfaces · Third-party integrations (auth flows, webhooks, data mapping, API scopes) · Auth & authorization · File handling, notifications, eventing · Environment config & external services · Operational tooling (purpose/inputs/behavior, not implementation) · Integration/acceptance test cases (happy paths + key failure modes).
>
> **Exclude:** Unimplemented features · Stack-specific details (no framework DSLs, ORM syntax, CLI flag names) · UI visual design (specify what it shows and does, not how it looks).
>
> **Tone:** Precise about behavior, not prescriptive about implementation. Mark unknowns as `[UNCLEAR: description]` rather than guessing.
