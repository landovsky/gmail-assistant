# Technology-Agnostic Specification

Analyze this system and produce a technology-agnostic specification that could be used to rebuild it from scratch on any suitable stack (e.g., Rails, NestJS, Express, Django).

## Output Constraints

### Structure
- Specification across up 12 to self-referential documents
- Choose a structure that makes sense for the system's complexity (e.g., separate docs for data model, API contracts, background jobs, integrations, business logic / domains, etc.)

### Interfaces — Identify and Specify All of Them

Inventory every interface the system exposes or consumes. Each interface is a first-class deliverable in the spec — none should be reduced to an afterthought. Common interface types (not exhaustive):

- **Web UI** — If the system has any browser-based interface (admin dashboard, user-facing app, etc.), describe it as a real, rendered UI — not as a set of JSON endpoints. Specify what it displays, what can be searched/filtered/sorted, what actions it supports, and any navigation structure.
- **JSON / REST API** — Document routes, request/response shapes, auth, pagination, error handling, status codes, and edge cases.
- **CLI tools** — Describe each tool's *purpose*, *inputs* (what information it needs), and *expected behavior/output*. Do not prescribe flag names, argument syntax, or invocation style — the rebuilder will implement these idiomatically for their stack (rake tasks, npm scripts, management commands, etc.).
- **Webhooks / inbound integrations** — Payload formats, validation, retry expectations, error handling.
- **Background workers / scheduled jobs** — Triggers, retry behavior, side effects, failure modes.
- **Pub/Sub or event-driven interfaces** — Topics, message formats, subscription semantics.

If the system has an interface type not listed above, identify and document it with the same rigor.

## What to Include

- **Data model** with relationships, validations, and domain invariants
- **All interfaces** as described above — every way the system communicates with users, operators, or external systems
- **Third-party integrations** (auth flows, webhook handling, data mapping, API scopes)
- **Auth & authorization model** (roles, permissions, token lifecycle)
- **File handling, notifications, and eventing patterns**
- **Environment configuration** and required external services
- **Operational tooling** — maintenance, debugging, deployment, and testing capabilities the system provides. Describe purpose, inputs, and expected behavior — not implementation details.
- **Integration/acceptance test cases** — end-to-end use cases that must pass regardless of stack, covering happy paths and key failure modes (separate from unit tests, which will be stack-specific)

## What to Exclude

- Anything not currently implemented — no aspirational features, no TODOs
- Stack-specific implementation details (no framework DSLs, no ORM syntax, no CLI flag names or argument syntax)
- UI visual design (layout, colors, CSS) — specify *what* the UI shows and does, not *how it looks*

## Tone & Approach

Write for a senior developer who has no prior context on this system. Be precise about behavior, not prescriptive about implementation.

**Important:** If you encounter behavior you can't fully determine from the provided code, mark it as `[UNCLEAR: description]` rather than guessing.
