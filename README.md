# Command Center — Meeting Notes Manager Mockup

A standalone prototype of the meeting notes manager module for the Infoblox Command Center. This is an engineering mockup built to validate the extraction and workflow logic before integration into the live system.

## Project Goals

- Build a working extraction agent that pulls action items from meeting transcripts
- Create a simple storage layer for action items (meeting-linked, owner-assigned, status-tracked)
- Develop a UI to view action items by meeting
- Generate draft emails in the meeting organizer's voice (not auto-send, for now)
- Establish a clear handoff point for engineering to integrate into the production Command Center

## Owners

- **Leland Nguyen** — Extraction agent, agent logic
- **Ryan Kang** — UI, frontend integration
- **Sponsor**: Hepsi Premkumar (Infoblox Command Center)

## Current Phase

**Manual transcript import + folder-based fallback for automation.** No live Teams connector yet; that's handled separately by IT/engineering.

### What we're building:
- ✅ Manual transcript upload (.txt or .vtt)
- ✅ Extraction agent (Claude-based, with defined rules for action items)
- ✅ Storage layer (SQLite or JSON, simple schema)
- ✅ Dashboard to view action items by meeting
- ✅ Draft email generation (human tone, organizer's voice)
- ❌ Live Teams transcript pull (out of scope, IT/engineering's job)
- ❌ Automated email sending (draft-only for now)

## Repository Structure

```
command-center-meeting-notes-mockup/
├── README.md                 (this file)
├── requirements.md           (detailed requirements & data model)
├── extraction-agent/         (extraction agent & prompts)
│   ├── agent.py
│   ├── prompts.md
│   └── test_transcripts/
├── storage/                  (storage layer)
│   ├── models.py             (data model schema)
│   ├── storage.py            (implementation)
│   └── migrations/
├── ui/                       (frontend)
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── tests/                    (test data)
    └── sample_transcripts/
```

## Getting Started

1. Clone the repo and create your working branch
2. See `requirements.md` for the full data model and constraints
3. Each team member works on their piece (extraction-agent or ui) on a separate branch
4. Submit pull requests for review before merging to main

## Key Constraints

- **Never invent an owner or due date.** If the transcript doesn't clearly assign one, leave it null.
- **Completed items should not clutter the active view.** They should be hidden from the default dashboard.
- **Email tone matters.** Draft emails should read like they're from the organizer, not an AI. No "Dear recipient, as an AI..." boilerplate.

## Technology (TBD)

- Extraction agent: Python + Claude API
- Storage: SQLite (initially)
- UI: [To be confirmed with Ryan]

---

**Status**: Prototype in development  
**Last updated**: 2026-09-01
