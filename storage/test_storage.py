"""Tests for the storage layer. Uses an in-memory SQLite DB — no mocking
needed, this is real, runnable code (unlike the extraction/email agents,
which need an API key).

Run with: pytest test_storage.py
"""

import pytest

from models import ActionItem, Meeting
from storage import Storage

EXTRACTION_RESULT = {
    "meeting_title": "Q3 Planning Sync",
    "meeting_date": "2026-09-03",
    "action_items": [
        {
            "description": "Finalize the Q3 roadmap document",
            "owner": "Sarah Patel",
            "due_date": None,
            "status": "completed",
        },
        {
            "description": "Review vendor proposals for the infrastructure upgrade",
            "owner": "Marcus Webb",
            "due_date": None,
            "status": "in_progress",
        },
        {
            "description": "Review the new dashboard mockups before shipping",
            "owner": None,
            "due_date": None,
            "status": "in_progress",
        },
    ],
}


@pytest.fixture
def store():
    with Storage(":memory:") as s:
        yield s


def test_create_and_get_meeting(store):
    meeting = Meeting(title="Weekly Sync", date="2026-09-08", organizer="Alex Chen")
    store.create_meeting(meeting)

    meetings = store.get_meetings()

    assert len(meetings) == 1
    assert meetings[0].id == meeting.id
    assert meetings[0].title == "Weekly Sync"
    assert meetings[0].organizer == "Alex Chen"


def test_action_item_rejects_invalid_status():
    with pytest.raises(ValueError, match="status"):
        ActionItem(meeting_id="m1", description="Do the thing", status="done")


def test_action_item_rejects_empty_description():
    with pytest.raises(ValueError, match="description"):
        ActionItem(meeting_id="m1", description="   ", status="in_progress")


def test_save_extraction_result_persists_meeting_and_items(store):
    meeting_id = store.save_extraction_result(EXTRACTION_RESULT, organizer="Alex Chen")

    meetings = store.get_meetings()
    assert len(meetings) == 1
    assert meetings[0].id == meeting_id
    assert meetings[0].title == "Q3 Planning Sync"
    assert meetings[0].organizer == "Alex Chen"

    all_items = store.get_action_items(meeting_id, include_completed=True)
    assert len(all_items) == 3
    owners = {item.owner for item in all_items}
    assert owners == {"Sarah Patel", "Marcus Webb", None}


def test_get_action_items_excludes_completed_by_default(store):
    meeting_id = store.save_extraction_result(EXTRACTION_RESULT)

    active_items = store.get_action_items(meeting_id)

    assert len(active_items) == 2
    assert all(item.status != "completed" for item in active_items)


def test_get_action_items_can_include_completed(store):
    meeting_id = store.save_extraction_result(EXTRACTION_RESULT)

    all_items = store.get_action_items(meeting_id, include_completed=True)

    assert len(all_items) == 3
    assert any(item.status == "completed" for item in all_items)


def test_update_status_appends_notes_addendum(store):
    meeting_id = store.save_extraction_result(EXTRACTION_RESULT)
    item = store.get_action_items(meeting_id)[0]

    store.update_status(item.id, "needs_follow_up", note="owner replied: waiting on vendor")

    updated = [i for i in store.get_action_items(meeting_id) if i.id == item.id][0]
    assert updated.status == "needs_follow_up"
    assert "owner replied: waiting on vendor" in updated.notes_addendum

    # Appending again should keep the earlier note, not overwrite it
    store.update_status(item.id, "completed", note="owner confirmed done")
    final = store.get_action_items(meeting_id, include_completed=True)
    final_item = [i for i in final if i.id == item.id][0]
    assert "waiting on vendor" in final_item.notes_addendum
    assert "owner confirmed done" in final_item.notes_addendum


def test_update_status_rejects_invalid_status(store):
    meeting_id = store.save_extraction_result(EXTRACTION_RESULT)
    item = store.get_action_items(meeting_id)[0]

    with pytest.raises(ValueError, match="status"):
        store.update_status(item.id, "done")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
