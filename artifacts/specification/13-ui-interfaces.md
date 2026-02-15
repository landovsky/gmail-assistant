# User Interface Specifications

## Overview

The system provides three browser-based interfaces for debugging, administration, and email inspection. All interfaces are HTML-based and served alongside the REST API.

## 1. Debug Email List Interface

**Purpose**: Quick overview and filtering of all processed emails with debug metadata.

**URL**: `/debug/emails`

**Authentication**: Required (if configured)

### Display Layout

**Top Navigation Bar** (fixed at top):
- "Email Debug" title
- Link to "All Emails" (clears filters)
- Link to "SQLAdmin" database browser
- "Full Sync" button (triggers immediate inbox sync)

**Filter Controls** (horizontal bar):
- Search input box (full-width):
  - Placeholder: "Search subject, body, sender, thread ID…"
  - Searches across: email subject, body content, sender email, thread ID, classification reasoning
  - Enter key triggers search
- Status dropdown:
  - Options: All, pending, drafted, rework_requested, sent, skipped, archived
  - Filters by email workflow status
- Classification dropdown:
  - Options: All, needs_response, action_required, payment_request, fyi, waiting
  - Filters by email category
- "Filter" button (applies current selections)
- "Reset" button (clears all filters)

**Results Table** (full-width):

| Column | Description | Interactive |
|--------|-------------|-------------|
| ID | Database row identifier | Clickable link to detail page |
| User | User email address | Read-only |
| Subject | Email subject (truncated to 60 chars) | Clickable link to detail page |
| Sender | Sender email address | Read-only |
| Classification | Category badge (colored) | Read-only |
| Draft Status | Workflow status badge (colored) | Read-only |
| Confidence | Classification confidence badge | Read-only |
| Events | Count of lifecycle events | Read-only |
| LLM | Count of LLM API calls | Read-only |
| Received | Timestamp when email arrived | Read-only |

**Badge Colors** (visual indicators):
- needs_response: Blue
- action_required: Purple
- payment_request: Orange
- fyi: Gray
- waiting: Cyan
- pending: Yellow
- drafted: Blue
- sent: Green
- skipped: Gray
- archived: Gray
- high confidence: Green
- medium confidence: Yellow
- low confidence: Orange

### Data Presentation

**Sorting**: Results ordered by ID descending (newest first)

**Pagination**: Fixed limit of 200 emails per page (no pagination controls shown)

**Empty State**: "No emails found." centered message when filters return no results

**Visual Theme**:
- Dark background (near-black)
- Monospace font throughout
- Card-based design with rounded corners
- Row hover highlighting for better scanning
- Color-coded badges for quick visual parsing

### User Interactions

**Filtering**:
1. User enters search term or selects dropdown values
2. Clicks "Filter" button or presses Enter
3. Page reloads with filtered results
4. URL preserves filter state (shareable links)

**Clicking Email**:
- Click ID or Subject → Navigate to detail page (`/debug/email/{id}`)

**Reset**:
- Click "Reset" → Clear all filters, return to `/debug/emails`

**Full Sync**:
- Click "Full Sync" → Confirmation dialog → POST request to sync API → Alert on success/failure

---

## 2. Debug Email Detail Interface

**Purpose**: Deep inspection of a single email with all processing history, LLM calls, and timeline visualization.

**URL**: `/debug/email/{email_id}`

**Authentication**: Required (if configured)

### Page Structure

**Top Navigation Bar** (same as list page):
- "Email Debug" title
- Link to "All Emails"
- Link to "SQLAdmin"
- "Full Sync" button
- **"Reclassify" button** (purple, triggers re-classification)
- **← prev / next →** navigation (right-aligned, navigates to adjacent email IDs)

**Email Metadata Card** (primary header):

**Large Header**:
- Subject (h2, prominent)
- Sender name and email (secondary text)
- Thread ID (monospace code block)
- Message ID (monospace code block)

**Badge Row** (visual status indicators):
- Classification badge
- Status badge
- Confidence badge
- Message count (number in thread)
- Resolved style (business/formal/informal)
- Detected language

**Metadata Grid** (8-field responsive layout):
- Received at: Timestamp when email arrived
- Processed at: When classification completed
- Drafted at: When draft was created
- Acted at: When final action taken (sent/archived)
- Draft ID: Gmail draft identifier
- Rework count: Number of rework iterations
- Vendor: Extracted vendor name (for invoices)
- DB ID: Database row identifier

**Additional Sections** (if data present):
- Reasoning box: Classification explanation (bordered, pre-formatted)
- Last rework instruction: User's most recent feedback
- Snippet: Email preview text

### Timeline Visualization

**Purpose**: Chronological view of all activity for this email across all data sources.

**Layout**: 3-column grid
1. Time column (90px, right-aligned): HH:MM:SS timestamps
2. Visual indicator (28px, centered): Vertical line with colored dots
3. Content column (flexible width): Event details

**Entry Types**:

**Events** (green dot):
- Title: Event type badge (classified, draft_created, sent_detected, etc.)
- Detail line: Human-readable description
- Additional info: Label ID, draft ID (if applicable)

**LLM Calls** (purple dot):
- Title: Call type badge (classify, draft, rework, context, agent)
- Detail line: Model name, token counts (prompt/completion/total), latency in ms
- Error indication: Red text if call failed

**Agent Runs** (cyan dot):
- Title: Profile name
- Detail line: Iterations count, status badge
- Error indication: Red text if error status

**Visual Features**:
- Chronological order (newest first)
- Color-coded dots for quick scanning
- Unified timeline merges all sources
- Empty state: "No timeline entries." if no data

### Events Section

**Table Display**:

| Column | Description |
|--------|-------------|
| ID | Event row identifier |
| Type | Event type badge |
| Detail | Text description |
| Label | Gmail label ID (if applicable) |
| Draft | Gmail draft ID (if applicable) |
| Time | Full timestamp |

**Section Features**:
- Header shows count badge (e.g., "Events (5)")
- Empty state: "No events recorded."
- All events for this email thread across all messages

### LLM Calls Section

**Table Display**:

| Column | Description |
|--------|-------------|
| ID | Call row identifier |
| Type | Call type badge (classify, draft, rework, context, agent) |
| Model | LLM model identifier |
| Prompt | Prompt token count |
| Compl. | Completion token count |
| Total | Total tokens used |
| Latency | Duration in milliseconds |
| Error | Error message (red if present) |
| Time | Timestamp |
| Prompts / Response | Expandable section (see below) |

**Expandable Prompts/Responses**:

Each LLM call has an expandable column with:
- **Expand all / Collapse all** buttons (top of cell)
- Three collapsible subsections:
  1. **system** - System prompt (full text)
  2. **user** - User message including email content (full text)
  3. **response** - LLM response (full text)

**Expansion UI**:
- Toggle indicator: ▸ (collapsed) / ▾ (expanded)
- Click label to toggle section
- Content displayed in:
  - Bordered box with dark background
  - Pre-formatted text (preserves whitespace)
  - Max height: 400px with scrollbar
  - Word-wrap enabled for long lines
- Each row's sections expand independently
- "Expand all" affects all sections in that row

**Section Features**:
- Header shows count badge
- Empty state: "No LLM calls recorded."

### Agent Runs Section

**Table Display**:

| Column | Description |
|--------|-------------|
| ID | Run row identifier |
| Profile | Agent profile name |
| Status | Status badge (running, completed, error, max_iterations) |
| Iterations | Number of loop iterations executed |
| Error | Error message (if status=error) |
| Started | Creation timestamp |
| Completed | Completion timestamp |
| Details | Expandable section (see below) |

**Expandable Details**:

Each agent run has two collapsible subsections:
1. **tool calls** - JSON array of tool invocations (pretty-printed)
2. **final message** - Agent's final output

**Features**:
- Same expandable UI pattern as LLM calls
- JSON formatting for tool_calls_log
- Empty state: "No agent runs recorded."

### Navigation Controls

**Adjacent Email Navigation**:
- **← prev** link: Navigate to email with ID-1 (only shown if exists)
- **next →** link: Navigate to email with ID+1 (only shown if exists)
- Right-aligned in top nav bar

**Action Buttons**:

**Reclassify**:
- Confirm dialog: "Reclassify this email? This will re-run the LLM classifier."
- On confirm: POST to `/api/emails/{id}/reclassify`
- Button shows "Queued…" and disables after click
- Alert shows job ID on success: "Reclassification queued: Job #456"

**Full Sync** (same as list page)

### Interactive Features

**JavaScript Functionality**:
- `toggle(id)`: Expand/collapse individual prompt/response sections
- `toggleAll(rowId, expand)`: Expand/collapse all sections in an LLM call row
- `reclassifyEmail(emailId)`: Confirmation dialog → API call → UI feedback
- `triggerFullSync()`: Confirmation dialog → API call → UI feedback

**Keyboard Navigation**:
- Browser back button: Return to list page
- Prev/next links: Keyboard accessible

---

## 3. Admin Database Browser Interface

**Purpose**: Generic database administration for viewing and managing all system data.

**URL**: `/admin/*`

**Authentication**: Required (if configured)

**Technology**: SQLAdmin-based interface (read-only mode)

### Navigation Structure

**Sidebar Menu** (always visible):
- "Gmail Assistant Admin" branding at top
- Custom "Full Sync" button (triggers inbox sync)
- Table list with icons:
  - 👤 Users
  - 🏷️ User Labels
  - ⚙️ User Settings
  - 🔄 Sync State
  - ✉️ Emails (with special debug icon integration)
  - 📜 Email Events
  - 🧠 LLM Calls
  - 📋 Jobs

**Main Content Area**:
- Breadcrumb navigation
- List view or detail view (depending on context)
- Standard SQLAdmin controls

### Table Views

Each table provides:

**List View Features**:
- Paginated table of records
- Column headers (sortable)
- Search box (searches designated columns)
- Filter controls (column-based filters)
- Row actions: View details (no edit/delete - read-only)

**Detail View Features**:
- All fields for selected record
- Related records (via foreign keys)
- Back button to list view

### Per-Table Specifications

#### Users Table
**Icon**: 👤

**List Columns**: id, email, display_name, is_active, onboarded_at, created_at

**Searchable**: email, display_name

**Sortable**: id, email, created_at

**Relationships**: Links to user's emails, labels, settings

#### User Labels Table
**Icon**: 🏷️

**List Columns**: user_id, label_key, gmail_label_id, gmail_label_name

**Searchable**: label_key, gmail_label_name

**Sortable**: user_id, label_key

**Purpose**: View Gmail label mappings per user

#### User Settings Table
**Icon**: ⚙️

**List Columns**: user_id, setting_key, setting_value

**Searchable**: setting_key

**Sortable**: user_id, setting_key

**Purpose**: View per-user configuration

#### Sync State Table
**Icon**: 🔄

**List Columns**: user_id, last_history_id, last_sync_at, watch_expiration

**Sortable**: user_id, last_sync_at

**Purpose**: Monitor Gmail sync status per user

#### Emails Table (Primary Debugging Interface)
**Icon**: ✉️

**List Columns**: id, user_id, subject, sender_email, classification, resolved_style, status, confidence, received_at

**Special Feature**: ID column shows debug icon (🔍) with link to `/debug/email/{id}`

**Searchable**: subject, sender_email, gmail_thread_id

**Sortable**: id, user_id, classification, status, received_at

**Detail View**: All 24 email columns including reasoning, snippet, timestamps, rework_count, etc.

**Default Sort**: ID descending (newest first)

#### Email Events Table
**Icon**: 📜

**List Columns**: id, user_id, gmail_thread_id, event_type, detail, created_at

**Searchable**: gmail_thread_id, event_type, detail

**Sortable**: id, user_id, event_type, created_at

**Default Sort**: created_at descending (newest first)

**Purpose**: Audit trail of all email lifecycle events

#### LLM Calls Table
**Icon**: 🧠

**List Columns**: id, user_id, gmail_thread_id, call_type, model, total_tokens, latency_ms, error, created_at

**Searchable**: gmail_thread_id, call_type, model

**Sortable**: id, user_id, call_type, total_tokens, latency_ms, created_at

**Detail View**: Includes full system_prompt, user_message, response_text (for deep debugging)

**Purpose**: Cost tracking and LLM performance analysis

#### Jobs Table
**Icon**: 📋

**List Columns**: id, user_id, job_type, status, attempts, error_message, created_at

**Searchable**: job_type, status

**Sortable**: id, user_id, job_type, status, created_at

**Purpose**: Monitor background job queue health

### Read-Only Constraints

**No Modifications Allowed**:
- Create button: Disabled
- Edit button: Disabled
- Delete button: Disabled

**Rationale**:
- Database modifications must go through validated API endpoints
- Prevents accidental data corruption
- Admin can view everything, change nothing

**Override**: Direct database access via SQL (for administrators who need to fix issues)

### Filtering & Sorting Capabilities

**Search**:
- Text input box at top of each table
- Searches across designated columns simultaneously
- Case-insensitive matching
- Live filtering as you type

**Column Filters**:
- Click filter icon next to column headers
- Filter types depend on column type:
  - Text: Contains, equals, starts with, ends with
  - Numbers: Equals, greater than, less than, between
  - Dates: Before, after, between
  - Booleans: True/false checkboxes
  - Enums: Dropdown selection

**Sorting**:
- Click column header to sort ascending
- Click again to sort descending
- Single-column sort only
- Default sort specified per table

**Pagination**:
- Page size selector (25, 50, 100 records per page)
- Page navigation controls (first, prev, next, last)
- Total record count displayed
- Current page indicator

### Visual Design

**Theme**:
- SQLAdmin/Tabler default theme
- Dark sidebar with light content area
- Clean, modern design
- Responsive grid layout

**Typography**:
- Sans-serif for UI text
- Monospace for code/IDs
- Clear hierarchy with font sizes

**Icons**:
- Font Awesome icons for each table
- Consistent icon usage throughout
- Visual indicators for actions

**Customization**:
- Custom layout template prevents subject column overflow
- Max-width: 300px on long text columns with ellipsis
- Email ID column shows custom debug icon link

---

## Interface Comparison

### When to Use Each Interface

**Debug Email List** (`/debug/emails`):
- Quick filtering by status or classification
- Finding specific emails by search
- Overview of recent processing activity
- Checking event/LLM call counts at a glance

**Debug Email Detail** (`/debug/email/{id}`):
- Deep troubleshooting of classification issues
- Viewing exact LLM prompts and responses
- Understanding timeline of email processing
- Inspecting agent tool calls
- Triggering reclassification

**Admin Database Browser** (`/admin`):
- Managing users and settings
- Viewing sync state across all users
- Analyzing job queue health
- Checking label mappings
- Exporting data for analysis
- Browsing relationships between tables

### Key Differences

| Feature | Debug List | Debug Detail | SQLAdmin |
|---------|-----------|--------------|----------|
| **Purpose** | Email overview | Email deep-dive | Database admin |
| **Scope** | Emails only | Single email | All tables |
| **Timeline** | No | Yes (merged 3 sources) | No |
| **LLM Prompts** | No | Yes (expandable) | Yes (detail view only) |
| **Agent Runs** | No | Yes | Not exposed |
| **Navigation** | Filters, search | Prev/next email | Table/detail views |
| **Actions** | Full sync | Reclassify, full sync | None (read-only) |
| **Relationships** | No | No | Yes (foreign keys) |
| **Export** | No | No | Yes (if enabled) |

### Missing from UI Interfaces

**Agent Runs in SQLAdmin**:
- Agent runs table exists in database but is not exposed in SQLAdmin
- Only visible via debug email detail interface
- Design decision or oversight [UNCLEAR]

**Web UI for Email Reading**:
- No interface for users to read emails (users use Gmail directly)
- System provides management/debugging only

**Bulk Actions**:
- No UI for bulk reclassification
- No UI for bulk status updates
- Would require API calls or direct database access

---

## Visual Design Principles

All interfaces follow consistent design principles:

**Dark Theme**:
- Background: Near-black (#0f1117)
- Cards/surfaces: Dark gray (#1a1d27)
- Text: Light gray/white
- Reduces eye strain for debugging sessions

**Typography**:
- Monospace everywhere (SF Mono, Fira Code, Consolas fallback)
- Reinforces technical/debugging context
- Improves readability of IDs and JSON

**Color Coding**:
- Consistent badge colors across all interfaces
- Status-based color semantics (green=good, red=error, yellow=pending)
- Visual scanning without reading text

**Information Density**:
- High density (fits many columns)
- Collapsible sections for large text
- Hover states for interactive elements
- Clear visual hierarchy

**Responsive Design**:
- Grid layouts adjust to screen size
- Mobile-friendly (though desktop-optimized)
- No horizontal scrolling except in code blocks

---

## Accessibility Considerations

**Keyboard Navigation**:
- All interactive elements keyboard-accessible
- Tab order follows visual flow
- Enter key triggers search

**Screen Readers**:
- Semantic HTML (table, th, td, etc.)
- Labels for form inputs
- ARIA attributes on expandable sections

**Color Contrast**:
- Sufficient contrast for text readability
- Don't rely solely on color (badges also have text)

**Text Scaling**:
- Relative font sizes support browser zoom
- Layout remains usable at 150% zoom

---

## Future Enhancements

Potential UI improvements not currently implemented:

**Debug List**:
- Pagination controls (currently fixed 200 limit)
- Bulk reclassification
- Export filtered results
- Saved filter presets

**Debug Detail**:
- Edit email metadata
- Delete email record
- Resend to pipeline
- Copy prompts to clipboard button

**SQLAdmin**:
- Expose agent_runs table
- Custom dashboard with aggregate stats
- Graphical timeline visualization
- Cost tracking dashboard

**General**:
- Dark/light theme toggle
- Customizable column visibility
- Advanced query builder
- Real-time updates (WebSocket)
