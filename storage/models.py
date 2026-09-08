"""Data model for meetings and action items.

Mirrors the SQLite schema in ../requirements.md ("Storage Layer
Specification"). Kept deliberately simple — this is an explicit placeholder
until Hepsi's team migrates it into her real database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

VALID_STATUSES = {"in_progress", "completed", "needs_follow_up"}


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Meeting:
    title: str
    date: str
    organizer: str | None = None
    summary: str | None = None
    agenda: list = field(default_factory=list)
    attendees: list = field(default_factory=list)
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_title": self.title,
            "meeting_date": self.date or None,
            "organizer": self.organizer,
            "summary": self.summary,
            "agenda": self.agenda if isinstance(self.agenda, list) else [],
            "attendees": self.attendees if isinstance(self.attendees, list) else [],
            "created_at": self.created_at,
        }


@dataclass
class ActionItem:
    meeting_id: str
    description: str
    status: str = "in_progress"
    owner: str | None = None
    due_date: str | None = None
    notes_addendum: str = ""
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(VALID_STATUSES)}, got {self.status!r}"
            )
        if not self.description or not self.description.strip():
            raise ValueError("description must be a non-empty string")
