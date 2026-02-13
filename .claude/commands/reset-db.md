Reset the database by calling the local dev server's reset API.

This clears all transient data (jobs, emails, email_events, sync_state) while preserving user accounts, labels, and settings. Use this to start classification from scratch.

## Instructions

1. Call the reset endpoint: `curl -s -X POST http://localhost:8000/api/reset`
2. Parse and display the JSON response showing deleted row counts per table
3. If the server isn't running, tell the user to start it with `/dev-env start`
