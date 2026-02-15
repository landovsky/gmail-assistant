# Technology-Agnostic Specification

Analyze this system and produce a technology-agnostic specification that could be used to rebuild it from scratch on any suitable stack (e.g., Rails, NestJS, Express).

## Output Constraints

### Structure
- Specification across up to 10 documents
- Choose a structure that makes sense for the system's complexity (e.g., separate docs for data model, API contracts, background jobs, integrations, etc.)

### Rebuild Requirements
- Web-based admin UI
- Relational database (assume SQL-compatible; specify schema, indices, constraints, and migrations conceptually)
- Google API integrations (specify which APIs, scopes, auth flows, and data sync behavior)
- JSON API for all client-facing endpoints (document routes, request/response shapes, auth, pagination, error handling)

## What to Include

- **Data model** with relationships, validations, and domain invariants
- **All API endpoints** with expected behavior, status codes, and edge cases
- **Background jobs / async processing** (triggers, retry behavior, side effects)
- **Third-party integrations** (auth flows, webhook handling, data mapping)
- **Auth & authorization model** (roles, permissions, token lifecycle)
- **File handling, notifications, and pub/sub or eventing patterns**
- **Environment configuration** and required external services
- **Integration/acceptance test cases** — a set of end-to-end use cases that must pass regardless of stack, covering happy paths and key failure modes (separate from unit tests, which will be written per-stack)

## What to Exclude

- Anything not currently implemented — no aspirational features, no TODOs
- Stack-specific implementation details (no framework DSLs, no ORM syntax)
- Admin UI layout/design (just document what admin can do, not how it looks)

## Tone & Approach

Write for a senior developer who has no prior context on this system. Be precise about behavior, not prescriptive about implementation.

**Important:** If you encounter behavior you can't fully determine from the provided code, mark it as `[UNCLEAR: description]` rather than guessing.
