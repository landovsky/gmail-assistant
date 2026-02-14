# Spec Philosophy & Maintenance

## What this is

A technology-agnostic behavioral specification of a production system — what it does, not how it's built. A senior developer with no prior context should be able to rebuild the system on any suitable stack producing functionally identical results.

## Core principles

**Behavior over implementation.** Describe what happens, not which framework method to call. "Return 404 when the resource doesn't exist" — not "use `find_by!` with a rescue."

**Mirror, not roadmap.** The spec reflects current production behavior. Nothing aspirational, no TODOs. If it's not shipped, it's not in the spec.

**One canonical definition.** Every entity, rule, or contract is defined in exactly one place. Other documents reference it, never redefine it.

**Honest about ambiguity.** When behavior couldn't be fully determined from code analysis, it's marked `[UNCLEAR: description]`. These are decision points for the rebuilder — resolve them, don't delete them silently.

## Keeping it current

**Spec changes ship with code changes.** No behavior change is done until the spec reflects it. Same PR, same branch.

**Re-generate to audit.** Periodically re-run the generation prompt against the codebase and diff the output against the maintained spec. This catches drift, missing coverage, and stale descriptions.

**Test cases are contracts.** The integration/acceptance test cases define the behavioral surface. When behavior changes, check whether test cases need updating too.

## Generation prompt

Preserved here for re-generation and audits. Feed it to an agent alongside the codebase.

> Analyze this system and produce a technology-agnostic specification that could be used to rebuild it from scratch on any suitable stack (e.g., Rails, NestJS, Express).
>
> **Output constraints:** Structure the spec across up to 10 documents. Choose a structure that makes sense for the system's complexity.
>
> **Rebuild constraints:** Web-based admin UI · SQL-compatible relational database · Google API integrations · JSON API for client-facing endpoints.
>
> **Include:** Data model with relationships/validations/invariants · All API endpoints with behavior/status codes/edge cases · Background jobs (triggers, retries, side effects) · Third-party integrations (auth flows, webhooks, data mapping) · Auth & authorization (roles, permissions, tokens) · File handling, notifications, eventing · Environment config & external services · Integration/acceptance test cases (happy paths + key failure modes).
>
> **Exclude:** Unimplemented features · Stack-specific details · Admin UI design.
>
> **Tone:** Precise about behavior, not prescriptive about implementation. Mark unknowns as `[UNCLEAR: description]` rather than guessing.