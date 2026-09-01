# Command Center Meeting Notes Manager — Requirements & Data Model

Extracted from the project brief. This is the specification for the mockup phase.

---

## Overview

This is a **prototype-to-engineering handoff**, not a shipped feature. We're building a standalone mockup that validates the extraction and workflow logic, then handing it to engineering for integration into the live Command Center.

**Key principle**: We don't have write access to Hepsi's live system or her database, and we don't want to risk breaking production. So we're building separately, with full control, and will hand it back for integration.

---

## End-State Vision (What This Becomes Eventually)

1. A meeting happens in Teams. A transcript is generated automatically.
2. The moment the meeting ends, an agent picks up that transcript with no manual step, extracts the meeting notes and action items, and stores them.
3. Each action item has: description, owner, due date (if discussed), and status (in progress / completed / needs follow-up). Completed items disappear from the active view.
4. The agent automatically emails the owner: "you have an action item, here it is." A few days later, it follows up asking for a status update.
5. The owner's reply is captured and updates the item's status and notes automatically.
6. A dashboard lets anyone select a meeting by title and see every action item tied to it, with live status.
7. Emails are sent as if written by the meeting organizer, in a normal human tone. Not obviously AI-generated boilerplate.

---

## Current Phase — What We're Actually Building

### What we ARE building:
- **Manual transcript import** — User pastes or uploads a transcript file (.txt or .vtt). No live Teams pull yet.
- **Folder-based fallback for automation** — As an interim design: a designated folder where a person drops a transcript, and a local script picks it up and runs extraction. (Hepsi's own suggested workaround for "can't connect to Teams yet.")
- **Working extraction agent** — Not an ad-hoc chat prompt. A properly configured agent/skill with explicit rules:
  - What counts as an action item
  - Who counts as an owner
  - How dates and status get extracted
  - Never inventing missing data
- **Draft emails, not auto-send** — Generate email content in the organizer's voice (human tone, specific to the action item). Let a human review/send it until the send pipeline is wired and tested.

### What we are NOT building (yet):
- **Live Teams transcript pull** — No direct connector from Claude/Glean to Teams. IT/engineering's job later.
- **Actual automated email sending** — Outlook integration not confirmed yet. Draft-generation only for now.
- **Backend API key / hosting configuration** — This is where Hepsi's build got stuck. We keep extraction agent dependencies isolated so a half-finished feature can't break the core flow.

---

## Data Model

### Action Item Schema

Every action item must have these fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | UUID or auto-increment | Yes | Unique identifier |
| `description` | string | Yes | What the action item actually is. Extracted from transcript. |
| `owner` | string | No (nullable) | Assignee's name. **Never invent.** If not clearly assigned in transcript, leave null. |
| `due_date` | string (ISO 8601) or null | No | Only if a date was explicitly discussed in the meeting. **Never invent.** |
| `status` | enum | Yes | One of: `in_progress`, `completed`, `needs_follow_up` |
| `meeting_title` | string | Yes | Title of the meeting this action item belongs to. |
| `meeting_date` | string (ISO 8601) | Yes | Date the meeting occurred. |
| `created_at` | timestamp | Yes | When the action item was created. |
| `notes_addendum` | string (appendable) | No | Running log of updates (e.g., "owner replied: still in progress as of [date]"). Grows as status updates come in. |

### Critical Rules

1. **Never invent an owner or due date.**
   - If the transcript doesn't clearly assign one, leave it null/unassigned.
   - A wrong action item attributed to the wrong person is worse than an unassigned one.

2. **Completed items should not clutter the active view.**
   - When an item's status is `completed`, it should be hidden from the default dashboard view.
   - Completed items are not deleted; they're archived visually.
   - A separate view or filter can show historical/completed items if needed.

3. **Email tone is critical.**
   - Emails should read as if written by the meeting organizer, not by "the agent" or an AI assistant.
   - Natural human tone: "Hi [name], you have an action item from [meeting]: [description]. Can you check on this and let me know status?"
   - NOT: "Dear recipient, as an AI assistant, I am writing to inform you..."
   - No boilerplate. Reference the specific action item, meeting, and context.

---

## Extraction Agent Specification

### Input
- A meeting transcript (.txt or .vtt format)
- Optionally: meeting title, meeting date, meeting organizer name

### Processing
The agent extracts:
- Meeting title (if not provided)
- Meeting date (if not provided)
- All action items mentioned, with:
  - Description (what needs to be done)
  - Owner (who it's assigned to, if mentioned)
  - Due date (only if explicitly discussed)
  - Any status indicators (e.g., "we'll complete this by Friday" → status = `in_progress`, due_date = [Friday's date])

### Output
A structured JSON or dict with:
```json
{
  "meeting_title": "Q3 Planning Session",
  "meeting_date": "2026-09-01",
  "action_items": [
    {
      "description": "Finalize the Q3 roadmap document",
      "owner": "Sarah Chen",
      "due_date": "2026-09-10",
      "status": "in_progress"
    },
    {
      "description": "Review vendor proposals for infrastructure upgrade",
      "owner": null,
      "due_date": null,
      "status": "in_progress"
    }
  ]
}
```

### Quality Rules for Extraction
- Only extract genuine action items (decisions, commitments, tasks). Don't include generic discussion points.
- If an owner's name is mentioned but unclear (e.g., "someone from the platform team"), leave owner as null rather than guessing.
- If a date is vague (e.g., "soon", "next month"), leave due_date as null.
- If multiple people are involved in one action, pick the primary owner or leave null if unclear.

---

## Storage Layer Specification

### Technology
Use **SQLite** or **JSON file store** for now. This is explicitly a placeholder — Hepsi's plan is to migrate into her real database once the mockup proves out. **Do not over-engineer the storage layer.**

### Simple Schema (SQLite example)

```sql
CREATE TABLE meetings (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  date TEXT NOT NULL,
  organizer TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE action_items (
  id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL,
  description TEXT NOT NULL,
  owner TEXT,
  due_date TEXT,
  status TEXT CHECK(status IN ('in_progress', 'completed', 'needs_follow_up')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  notes_addendum TEXT,
  FOREIGN KEY(meeting_id) REFERENCES meetings(id)
);
```

### Operations
- **Create**: Insert new action items after extraction.
- **Read**: Fetch all action items for a given meeting; filter by status (e.g., exclude completed).
- **Update**: Update status and notes_addendum when owner replies or status changes.
- **Delete**: Not needed for the MVP.

---

## UI Specification

### Views

#### 1. Meeting Selector
- Display a list of all meetings (by title and date).
- User selects a meeting to view its action items.

#### 2. Action Items Dashboard (Meeting View)
- Show all **active** action items for the selected meeting (status != `completed`).
- Display for each item:
  - Description
  - Owner (or "Unassigned" if null)
  - Due date (or blank if null)
  - Current status (in_progress / completed / needs_follow_up)
- Provide a way to mark an item as completed (this moves it out of active view).
- Optionally show a link to view the generated draft email for this item.

#### 3. Transcript Upload
- A form to upload or paste a transcript (.txt or .vtt).
- Optionally: fields to manually specify meeting title, date, organizer name (if not in transcript).
- Button to "Extract and Save" — runs the extraction agent and stores results.

---

## Email Draft Generation Specification

### Trigger
- When an action item is created, or when initiating a status check.

### First Email (Assignment)
**To**: Action item owner  
**From**: Meeting organizer (appears as "from", but this is draft content, not actually sent)  
**Subject**: Natural, e.g., "Action Item from [Meeting Title]" or just "Follow-up: [Meeting Title]"  
**Body**: Natural human tone.

Example:
```
Hi Sarah,

During today's Q3 Planning Session, we identified the following action for you:

Finalize the Q3 roadmap document — due by Sept 10th.

Can you let me know if you have any blockers or need support from the team?

Thanks,
[Meeting Organizer Name]
```

### Follow-up Email (Status Check)
Sent a few days after the first email if no status update received.

Example:
```
Hi Sarah,

Just checking in on the Q3 roadmap document action item from our Sept 1 meeting. Still on track for Sept 10?

Let me know how it's going.

Thanks,
[Meeting Organizer Name]
```

### Draft Generation Rules
- Reference the specific meeting title, date, and action item description.
- Use the organizer's name (from the meeting data).
- Use the owner's name.
- Write in a casual, professional tone (as if the organizer is writing it).
- No templated boilerplate. Each email should feel personalized to the specific action item.

---

## Test Data

Use real (but non-sensitive) meeting transcripts for testing:
- `.txt` or `.vtt` format
- Confirm the agent correctly identifies action items
- Confirm it doesn't fabricate owners or dates
- Confirm completed items are correctly excluded from the active view
- Confirm draft emails read naturally and don't sound AI-generated

---

## Out of Scope (Explicitly)

- **Live Teams transcript pull** — Not built; handled separately by IT/engineering.
- **Actual automated email sending** — Draft-only; Outlook integration not confirmed.
- **Backend API key / hosting configuration** — Keep extraction agent dependencies isolated.
- **Complex UI features** — No real-time collaboration, no advanced filtering (for MVP).
- **Database migration** — Storage is simple placeholder; engineering will migrate later.

---

## Handoff Criteria

This mockup is ready to hand off to engineering when:

1. ✅ Extraction agent reliably extracts action items without fabricating owners or dates
2. ✅ Storage layer cleanly separates data model from implementation
3. ✅ UI cleanly shows active (non-completed) action items by meeting
4. ✅ Draft email generation produces natural, organizer-voiced emails
5. ✅ All pieces integrate without breaking (manual transcript import → extraction → storage → UI display)
6. ✅ Clear documentation of data model and constraints for engineering to build on

---

**Status**: Specification locked for mockup phase  
**Last updated**: 2026-09-01
