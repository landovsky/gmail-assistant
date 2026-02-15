# Email Lifecycle and State Machine

## Email Status States

The email lifecycle is managed through a state machine with six states:

### pending
- **Initial state** after classification
- **Meaning**: Email classified, awaiting draft generation (if needs_response)
- **Next states**: drafted, skipped

### drafted
- **Triggered by**: Draft job successfully creates Gmail draft
- **Meaning**: AI-generated draft ready for user review in Gmail
- **Gmail state**: Draft exists, Outbox label applied
- **Next states**: sent, archived, rework_requested

### rework_requested
- **Triggered by**: User applies Rework label
- **Meaning**: User provided feedback, regenerating draft
- **Temporary state**: Quickly transitions back to drafted
- **Next states**: drafted, skipped (if limit reached)

### sent
- **Triggered by**: Draft deletion detected (user sent the email)
- **Meaning**: User sent the draft response
- **Gmail state**: Draft no longer exists, message in Sent folder
- **Terminal state**: No further automated transitions
- **Next states**: archived (only via manual Done label)

### skipped
- **Triggered by**:
  - Classification ≠ needs_response (action_required, fyi, waiting, payment_request)
  - Rework limit reached (3 attempts)
- **Meaning**: No draft needed or draft generation abandoned
- **Next states**: archived

### archived
- **Triggered by**: User applies Done label
- **Meaning**: User marked thread as complete
- **Gmail state**: All AI labels removed, thread archived from inbox
- **Terminal state**: No further automated transitions

## State Transition Diagram

```
                     ┌─────────────┐
                     │ New Email   │
                     └──────┬──────┘
                            │
                            ▼
                     ┌─────────────┐
                     │ Classified  │
                     └──────┬──────┘
                            │
                   ┌────────┴────────┐
                   │                 │
                   ▼                 ▼
         ┌──────────────┐    ┌─────────────┐
         │   pending    │    │   skipped   │
         └──────┬───────┘    └──────┬──────┘
                │                   │
                ▼                   │
         ┌──────────────┐           │
         │   drafted    │◄──┐       │
         └──────┬───────┘   │       │
                │            │       │
         ┌──────┴───────┐   │       │
         │      │       │   │       │
         ▼      ▼       ▼   │       │
      ┌────┐ ┌────┐ ┌────┐ │       │
      │sent│ │Done│ │Work│─┘       │
      └─┬──┘ └─┬──┘ └────┘         │
        │      │  rework_requested  │
        │      │                    │
        │      │         ┌──────────┘
        │      │         │
        └──────┴─────────┘
               │
               ▼
        ┌─────────────┐
        │  archived   │
        └─────────────┘
```

## State Transition Events

### Classification → pending
- **Trigger**: Email classified as needs_response
- **Actions**:
  - Create email record with status=pending
  - Apply classification label (Needs Response)
  - Enqueue draft job
  - Log event: classified

### Classification → skipped
- **Trigger**: Email classified as fyi, action_required, payment_request, or waiting
- **Actions**:
  - Create email record with status=skipped
  - Apply appropriate classification label
  - Log event: classified

### pending → drafted
- **Trigger**: Draft job successfully creates Gmail draft
- **Actions**:
  - Update status to drafted
  - Store draft_id
  - Set drafted_at timestamp
  - Remove classification label (Needs Response)
  - Add Outbox label
  - Log event: draft_created

### drafted → rework_requested → drafted
- **Trigger**: User applies Rework label
- **Actions**:
  - Extract rework instructions from draft
  - Increment rework_count
  - Store last_rework_instruction
  - Generate new draft
  - Trash old draft
  - Store new draft_id
  - Keep status as drafted
  - Keep Outbox label (or move to Action Required if limit reached)
  - Log event: draft_reworked

### drafted → skipped (rework limit)
- **Trigger**: rework_count reaches 3 and user requests another rework
- **Actions**:
  - Update status to skipped
  - Remove Outbox label
  - Add Action Required label
  - Add warning to draft about limit
  - Log event: rework_limit_reached

### drafted → sent
- **Trigger**: Draft deletion detected (messagesDeleted in History API)
- **Actions**:
  - Verify draft_id no longer exists in Gmail
  - Update status to sent
  - Set acted_at timestamp
  - Remove Outbox label
  - Log event: sent_detected

### drafted/sent/skipped → archived
- **Trigger**: User applies Done label
- **Actions**:
  - Update status to archived
  - Set acted_at timestamp
  - Remove all AI labels (parent + children)
  - Remove INBOX label (archives thread)
  - Log event: archived

### waiting → reclassified
- **Trigger**: New reply arrives on waiting thread (message_count increases)
- **Actions**:
  - Remove Waiting label
  - Re-run classification pipeline
  - May transition to needs_response → drafted
  - Log event: waiting_retriaged

## Label Management

### Gmail Labels Used

**Parent Label**: 🤖 AI

**Classification Labels** (mutually exclusive):
- 🤖 AI/Needs Response
- 🤖 AI/Action Required
- 🤖 AI/Payment Requests
- 🤖 AI/FYI
- 🤖 AI/Waiting

**Workflow Labels**:
- 🤖 AI/Outbox (draft ready for review)
- 🤖 AI/Rework (user requesting changes)
- 🤖 AI/Done (user marking complete)

### Label Application Rules

**On Classification**:
- Apply parent label (🤖 AI)
- Apply classification label based on category
- Thread visible in respective Gmail label view

**On Draft Created**:
- Remove classification label (Needs Response)
- Add Outbox label
- Thread visible in Outbox view

**On Rework Request**:
- User manually applies Rework label
- System detects via labelsAdded History event
- Triggers rework job

**On Done**:
- User manually applies Done label
- System detects via labelsAdded History event
- Triggers cleanup job
- All AI labels removed
- INBOX label removed (archives)

**Batch Operations**:
- Labels applied/removed via batch modify API for efficiency
- Single API call can update entire thread

## Lifecycle Handlers

### Done Handler
**Purpose**: Clean up completed threads

**Inputs**:
- User ID
- Thread ID

**Actions**:
1. Remove all AI labels from thread
2. Remove INBOX label (archives thread)
3. Update email status to archived
4. Set acted_at timestamp
5. Log event: archived

**Result**: Thread disappears from AI label views and inbox

### Sent Detection Handler
**Purpose**: Detect when user sends AI-generated draft

**Inputs**:
- User ID
- Thread ID
- Draft ID (from email record)

**Actions**:
1. Check if draft_id still exists in Gmail
2. If not found → user likely sent it:
   - Update status to sent
   - Set acted_at timestamp
   - Remove Outbox label
   - Log event: sent_detected
3. If still exists → false alarm, no action

**Trigger**: messagesDeleted event in Gmail History API

**Note**: Not 100% certain (draft could be manually deleted), but high probability

### Waiting Retriage Handler
**Purpose**: Reclassify waiting threads when replies arrive

**Inputs**:
- User ID
- Thread ID

**Actions**:
1. Check current message_count vs. stored count
2. If increased (new message arrived):
   - Remove Waiting label
   - Trigger reclassification
   - May create draft if now needs_response
   - Log event: waiting_retriaged

**Trigger**: messagesAdded on thread with Waiting label

### Rework Handler
**Purpose**: Regenerate draft with user feedback

**Inputs**:
- User ID
- Thread ID

**Actions**:
1. Fetch existing draft from Gmail
2. Extract instruction above ✂️ marker
3. Check rework_count < 3
4. If under limit:
   - Generate new draft with feedback
   - Trash old draft
   - Create new draft
   - Increment rework_count
   - Keep Outbox label
   - Log event: draft_reworked
5. If at limit:
   - Update status to skipped
   - Move to Action Required label
   - Add warning to draft
   - Log event: rework_limit_reached

**Trigger**: labelsAdded with Rework label

## Edge Cases

### User Edits Draft Directly
- Draft modified without rework label → No system action
- User can manually edit without triggering LLM regeneration
- When sent, still detected as sent via draft deletion

### User Deletes Draft Manually
- Draft deleted without sending → Detected as sent (false positive)
- Acceptable trade-off: User can re-apply Needs Response label if needed

### Reclassification While Drafted
- If email reclassified away from needs_response while draft exists:
  - Old draft trashed
  - Status updated to skipped
  - New classification label applied

### Multiple Rework Labels Applied
- Rework job runs once per label addition
- Multiple rapid additions may queue multiple jobs
- Deduplication logic prevents duplicate processing

### User Sends Original Email, Not Draft
- User writes own reply instead of using AI draft
- Draft remains in Gmail
- Not detected as sent (draft still exists)
- User should apply Done label to clean up

## Audit Trail

Every state transition generates:
- Email record update (status, timestamps)
- Event log entry (event_type, detail, labels, draft_id)
- LLM call log (if draft generation involved)

**Event Types**:
- classified
- draft_created
- draft_trashed
- draft_reworked
- sent_detected
- archived
- rework_limit_reached
- waiting_retriaged
- label_added
- label_removed
- error

All events include:
- Timestamp
- User ID
- Thread ID
- Optional: label_id, draft_id, detail

## State Invariants

**Database Constraints**:
- Email status must be valid enum value
- Classification must be valid enum value
- Foreign key to user must exist
- Unique (user_id, gmail_thread_id)

**Business Rules**:
- Only needs_response emails get drafts
- Rework count ≤ 3
- Status transitions follow state machine
- Labels match status (drafted = Outbox, skipped = classification label)
- Timestamps are monotonic (created ≤ processed ≤ drafted ≤ acted)

## Manual Override

Users can manually:
- Apply any label to any thread (triggers corresponding handler)
- Remove AI labels (system respects user choice)
- Move threads to Done (archives regardless of status)
- Apply Needs Response to non-response threads (triggers manual_draft job)
- Send drafts, edit drafts, delete drafts (all handled gracefully)

The system is designed to assist, not constrain, user email workflow.
