"""SQLite storage layer for meetings and action items.

Explicit placeholder per requirements.md — SQLite only, deliberately not
over-engineered. Hepsi's team plans to migrate this into her real database
once the mockup proves out.

Typical usage: pass the exact dict returned by
extraction-agent/agent.py's extract_action_items() straight into
save_extraction_result() to persist a meeting and all its action items.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from models import ActionItem, Meeting, VALID_STATUSES

DEFAULT_DB_PATH = Path(__file__).parent / "command_center.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  date TEXT NOT NULL,
  organizer TEXT,
  summary TEXT,
  agenda TEXT,
  attendees TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_items (
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
"""

_MIGRATIONS = [
    "ALTER TABLE meetings ADD COLUMN summary TEXT",
    "ALTER TABLE meetings ADD COLUMN agenda TEXT",
    "ALTER TABLE meetings ADD COLUMN attendees TEXT",
]


class Storage:
    """Thin wrapper around one SQLite connection."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._run_migrations()

    def _run_migrations(self) -> None:
        for sql in _MIGRATIONS:
            try:
                self._conn.execute(sql)
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # ---- Create ----

    def create_meeting(self, meeting: Meeting) -> str:
        self._conn.execute(
            "INSERT INTO meetings (id, title, date, organizer, summary, agenda, attendees, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                meeting.id,
                meeting.title,
                meeting.date,
                meeting.organizer,
                meeting.summary,
                json.dumps(meeting.agenda if isinstance(meeting.agenda, list) else []),
                json.dumps(meeting.attendees if isinstance(meeting.attendees, list) else []),
                meeting.created_at,
            ),
        )
        self._conn.commit()
        return meeting.id

    def create_action_item(self, item: ActionItem) -> str:
        self._conn.execute(
            """INSERT INTO action_items
               (id, meeting_id, description, owner, due_date, status, created_at, notes_addendum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.id,
                item.meeting_id,
                item.description,
                item.owner,
                item.due_date,
                item.status,
                item.created_at,
                item.notes_addendum,
            ),
        )
        self._conn.commit()
        return item.id

    def save_extraction_result(self, extraction: dict, organizer: str | None = None) -> str:
        """Persist the exact dict shape returned by agent.extract_action_items().

        Creates one meeting row plus one action_items row per item. Returns
        the new meeting_id.
        """
        meeting = Meeting(
            title=extraction["meeting_title"] or "Untitled meeting",
            date=extraction["meeting_date"] or "",
            organizer=organizer,
            summary=extraction.get("summary"),
            agenda=extraction.get("agenda") or [],
            attendees=extraction.get("attendees") or [],
        )
        self.create_meeting(meeting)

        for item_data in extraction["action_items"]:
            item = ActionItem(
                meeting_id=meeting.id,
                description=item_data["description"],
                owner=item_data.get("owner"),
                due_date=item_data.get("due_date"),
                status=item_data.get("status", "in_progress"),
            )
            self.create_action_item(item)

        return meeting.id

    # ---- Read ----

    def _row_to_meeting(self, row: sqlite3.Row) -> Meeting:
        d = dict(row)
        d["agenda"] = json.loads(d.get("agenda") or "[]")
        d["attendees"] = json.loads(d.get("attendees") or "[]")
        return Meeting(**d)

    def get_meetings(self) -> list[Meeting]:
        rows = self._conn.execute("SELECT * FROM meetings ORDER BY date DESC, created_at DESC").fetchall()
        return [self._row_to_meeting(r) for r in rows]

    def get_meeting_with_items(self, meeting_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if row is None:
            return None
        meeting = self._row_to_meeting(row)
        result = meeting.to_dict()
        items = self._conn.execute(
            "SELECT * FROM action_items WHERE meeting_id = ? ORDER BY created_at ASC", (meeting_id,)
        ).fetchall()
        result["action_items"] = [
            {
                "id": r["id"],
                "description": r["description"],
                "owner": r["owner"],
                "due_date": r["due_date"],
                "status": r["status"],
                "notes_addendum": r["notes_addendum"] or "",
            }
            for r in items
        ]
        return result

    def get_action_items(self, meeting_id: str, include_completed: bool = False) -> list[ActionItem]:
        query = "SELECT * FROM action_items WHERE meeting_id = ?"
        params: tuple = (meeting_id,)
        if not include_completed:
            query += " AND status != 'completed'"
        query += " ORDER BY created_at ASC"
        rows = self._conn.execute(query, params).fetchall()
        return [ActionItem(**dict(row)) for row in rows]

    # ---- Update ----

    def update_status(self, item_id: str, status: str, note: str | None = None) -> None:
        """Update an action item's status, optionally appending a
        timestamped line to notes_addendum (e.g. "owner replied: still in
        progress"). notes_addendum is a running log, never overwritten.
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}")

        if note:
            row = self._conn.execute(
                "SELECT notes_addendum FROM action_items WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"No action item with id {item_id!r}")
            existing = row["notes_addendum"] or ""
            today = datetime.now(timezone.utc).date().isoformat()
            appended = f"{existing}\n[{today}] {note}".strip()
            self._conn.execute(
                "UPDATE action_items SET status = ?, notes_addendum = ? WHERE id = ?",
                (status, appended, item_id),
            )
        else:
            self._conn.execute(
                "UPDATE action_items SET status = ? WHERE id = ?", (status, item_id)
            )
        self._conn.commit()
