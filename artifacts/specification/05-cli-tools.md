# CLI Tools and Operational Commands

## Server Entry Point

**Purpose**: Starts the web server that processes Gmail emails with AI classification and draft generation

**Inputs**:
- Application configuration from YAML file
- Environment variables for overrides
- Database connection settings
- OAuth credentials files

**Expected Behavior/Output**:
- Launches web server on configured host/port (default: localhost:8000)
- Initializes database schema and runs migrations
- Starts background worker pool for async job processing
- Starts scheduler for Gmail watch renewal and fallback sync
- Serves REST API endpoints, admin UI, and debug interfaces
- Logs operational events at configured level

## Email Classification Debugger

**Purpose**: Interactively debug email classification by running emails through the two-tier classification pipeline with detailed step-by-step output

**Inputs**:
- Email metadata: sender email, sender name, subject, body
- Source options: interactive prompts, inline arguments, file input, or database thread ID
- Blacklist patterns for sender filtering
- Contact configuration for style resolution
- Optional: LLM API key for live classification

**Expected Behavior/Output**:
- Shows rule engine step-by-step evaluation with pattern matching
- Displays which classification rule matched (if any)
- Shows confidence level and reasoning
- Previews LLM prompt that would be sent for Tier 2 classification
- Optionally makes live LLM call and shows classification result
- Color-coded terminal output showing classification category, confidence, decision path
- Helps identify why emails are classified incorrectly

## Context Gathering Debugger

**Purpose**: Debug the context gathering system that finds related email threads using LLM-generated search queries

**Inputs**:
- Email metadata: sender, subject, body
- Source: manual input or database thread ID
- Optional: live Gmail API access for actual search execution

**Expected Behavior/Output**:
- Calls LLM to generate Gmail search queries (up to 3)
- Shows raw LLM response and parsed queries
- Optionally executes queries against live Gmail account
- Displays found threads with deduplication
- Shows formatted context block as it appears in draft prompts
- Helps debug why draft responses lack proper context

## Classification Test Suite

**Purpose**: Validate classification accuracy against predefined test cases with confusion matrix analysis

**Inputs**:
- Test fixture YAML file with test cases
- Filter options: specific category, case ID, rules-only, LLM-only
- Blacklist and contact configuration
- LLM API key (unless using rules-only mode)

**Expected Behavior/Output**:
- Runs classification engine against each test case
- Shows pass/fail status with expected vs actual category
- Tracks tier (rules vs LLM) for each classification
- Computes accuracy percentage
- Generates confusion matrix for failed cases
- Color-coded terminal output with per-case reasoning
- Exit code 0 if all tests pass, 1 if any failures

## Gmail Label Cleanup

**Purpose**: Remove all AI workflow labels from inbox messages (for reset or migration scenarios)

**Inputs**:
- Gmail OAuth credentials
- List of AI label IDs
- Dry run mode (default) or delete mode

**Expected Behavior/Output**:
- Searches for all messages with any AI label
- Shows preview of affected messages (subject + thread ID)
- In dry run: displays count and sample messages
- In delete mode: batch removes labels from all messages
- Does NOT delete messages, only removes labels
- Useful for resetting workflow state

## Draft Cleanup

**Purpose**: Delete AI-generated Gmail drafts that contain the rework marker

**Inputs**:
- Gmail OAuth credentials
- Dry run mode (default) or delete mode

**Expected Behavior/Output**:
- Lists all Gmail drafts
- Identifies drafts containing rework marker (indicates AI-generated)
- Shows preview with subject lines
- In delete mode: permanently deletes drafts from Gmail
- Reports count of deleted drafts
- Helps clean up stale AI drafts that were never sent

## Full Sync Trigger

**Purpose**: Trigger a complete inbox scan to classify all untagged emails

**Inputs**:
- Environment selection (development or production)
- Basic auth credentials (if configured)
- Optional: reset flag to wipe database first

**Expected Behavior/Output**:
- Optionally clears database (jobs, emails, events, sync state)
- Calls sync API endpoint with full=true parameter
- Clears sync state to force full inbox scan
- Enqueues sync job for background processing
- Returns JSON response with queue status
- User should monitor server logs for progress

## Database Reset

**Purpose**: Clear all transient data while preserving user accounts and configuration

**Inputs**:
- Environment selection (development or production)
- Basic auth credentials (if configured)
- Confirmation prompt for production

**Expected Behavior/Output**:
- Deletes all rows from: jobs, emails, email_events, sync_state
- Preserves: users, labels, settings, migrations
- Returns JSON with per-table deletion counts
- Resets processing state without losing user setup
- Useful for development testing or recovering from errors

## Test Email Sender

**Purpose**: Send synthetic test emails to exercise the classification and drafting pipeline

**Inputs**:
- Classification target (needs_response, action_required, payment_request, fyi, waiting)
- Communication style (formal, casual, terse, verbose, passive_aggressive, friendly)
- Recipient email address
- Count of emails to send
- Delay between emails (minutes)

**Expected Behavior/Output**:
- Generates realistic test email content matching specified classification
- Sends via Gmail integration
- Delays between emails when sending multiple
- Emails arrive in inbox and trigger classification pipeline
- Useful for end-to-end testing

## Session List Tool

**Purpose**: List all development sessions for this project with metadata

**Inputs**:
- Session storage path
- Optional: minimum turn count filter
- Optional: dev-only flag (filter out automated runs)

**Expected Behavior/Output**:
- Scans all session files
- Extracts: session ID, timestamp, file size, user/assistant turn counts, first user message
- Sorts by total turns (most active first)
- Outputs formatted table or JSON
- Helps identify relevant development sessions for debugging

## Session Message Extractor

**Purpose**: Extract and filter messages from a development session for analysis

**Inputs**:
- Session ID (full or partial)
- Filter mode: all messages, user-only, or assistant messages with error keywords
- Maximum message length

**Expected Behavior/Output**:
- Loads session file
- Strips system/command tags for readability
- Extracts user messages and optionally assistant messages
- Filters assistant messages for error/fix indicators
- Outputs numbered messages with truncation
- Helps debug sessions and extract conversation history

## Kubernetes Secret Updater

**Purpose**: Update Kubernetes secrets for production deployment (API keys and OAuth credentials)

**Inputs**:
- Environment variables: API keys, admin credentials
- Local files: OAuth credentials, tokens
- Kubernetes namespace (default: default)

**Expected Behavior/Output**:
- Deletes existing secrets
- Creates new secrets from environment variables and files
- Requires manual pod restart to pick up changes
- Provides kubectl command for restart
- Used for production deployment updates

## Administrative APIs

### User Management
- **List users**: Show all active users with onboarding status
- **Create user**: Add new user account
- **Get user settings**: Retrieve all settings for a user
- **Update user setting**: Modify single setting value
- **Get user labels**: Fetch Gmail labels for a user
- **Get user emails**: List emails with optional filtering by status/classification

### System Operations
- **Health check**: Verify service is running (returns status: ok)
- **Reset database**: Clear transient data (jobs, emails, events, sync state)
- **Trigger sync**: Enqueue sync job (full=true forces complete inbox scan)

### Authentication & Watch Management
- **Bootstrap OAuth**: Trigger OAuth browser consent flow and onboard first user
- **Register Gmail watch**: Set up push notifications for user(s)
- **Show watch status**: Display watch state and expiration for all users

### Briefing/Dashboard
- **Get inbox briefing**: Fetch inbox summary by classification with action item counts

### Debug & Reclassification
- **Get email debug data**: Retrieve all debug data for an email (events, LLM calls, agent runs, timeline, summary)
- **List emails with search**: Search and filter emails with full-text search
- **Force reclassification**: Re-run classification on an email (enqueues classify job with force flag)

### Webhook
- **Receive Gmail push notifications**: Public endpoint for Gmail Pub/Sub callbacks

### HTML Interfaces
- **Email list page**: HTML interface with search/filter UI
- **Email debug page**: Unified debug view (timeline, events, LLM calls, agent runs)
- **Database browser**: Read-only admin interface for all tables
- **Root redirect**: Redirects to email list page

## Test Suite

**Purpose**: Comprehensive test coverage for classification, drafting, database, lifecycle, agents, and integration flows

**Inputs**:
- Test files (118 tests total)
- Optional: LLM API key for end-to-end tests
- Optional: dev server for smoke tests
- Test markers: e2e (requires LLM API), smoke (requires running server)

**Expected Behavior/Output**:
- Runs async tests
- Tests classification rules and LLM integration
- Tests draft generation and rework loops
- Tests database repositories and migrations
- Tests lifecycle state machine transitions
- Tests agent framework and tool registry
- Tests Gmail API retry logic
- Color-coded pass/fail output
- Coverage reports

## Tool Categories

### Development/Debug Tools
- Classification debugger - Interactive debugging for classification pipeline
- Context gathering debugger - Debug related thread search
- Test suite - Validate classification accuracy
- Session analysis - List and extract session messages

### Maintenance Tools
- Database reset - Clear transient data
- Label cleanup - Remove AI labels from messages
- Draft cleanup - Delete AI-generated drafts
- Full inbox sync - Trigger complete scan
- Secret management - Update production credentials

### API/Web Interfaces
- REST endpoints - User management, email operations, sync triggering, reclassification
- HTML debug interfaces - Email inspection with timeline visualization
- Database browser - Read-only admin interface

## Common Patterns

All tools follow consistent patterns:
- Dry-run defaults for destructive operations
- Environment selection (development/production)
- Color-coded terminal output for readability
- Detailed logging for debugging
- Confirmation prompts for production operations
