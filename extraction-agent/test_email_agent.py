"""Tests for the email draft agent. Mocks the Claude API call so tests run
without a network connection or API key.

Run with: pytest test_email_agent.py
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from email_agent import _validate_email, draft_email, draft_email_batch, load_email_system_prompt

MEETING_TITLE = "Q3 Planning Sync"
MEETING_DATE = "2026-09-03"
ORGANIZER = "Alex Chen"

ASSIGNED_ITEM = {
    "description": "Review vendor proposals for the infrastructure upgrade",
    "owner": "Marcus Webb",
    "due_date": None,
    "status": "in_progress",
}

UNASSIGNED_ITEM = {
    "description": "Review the new dashboard mockups before shipping",
    "owner": None,
    "due_date": None,
    "status": "in_progress",
}

EXPECTED_EMAIL = {
    "subject": "Action item from Q3 Planning Sync",
    "body": (
        "Hi Marcus,\n\n"
        "From today's Q3 Planning Sync, you're set to review the vendor "
        "proposals for the infrastructure upgrade — no firm deadline yet, "
        "just whenever you can get to it in the next couple weeks.\n\n"
        "Let me know if you need anything from the team to get started.\n\n"
        "Thanks,\nAlex"
    ),
}


def _make_mock_client(response_text: str) -> MagicMock:
    mock_client = MagicMock()
    mock_client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=response_text)]
    )
    return mock_client


def test_load_email_system_prompt_contains_key_rules():
    prompt = load_email_system_prompt()
    assert "As an AI" in prompt  # named as something to avoid
    assert "subject" in prompt and "body" in prompt


def test_draft_email_rejects_unassigned_owner():
    mock_client = _make_mock_client(json.dumps(EXPECTED_EMAIL))
    with pytest.raises(ValueError, match="no owner"):
        draft_email("assignment", MEETING_TITLE, MEETING_DATE, ORGANIZER, UNASSIGNED_ITEM, client=mock_client)
    mock_client.messages.create.assert_not_called()


def test_draft_email_rejects_invalid_email_type():
    mock_client = _make_mock_client(json.dumps(EXPECTED_EMAIL))
    with pytest.raises(ValueError, match="email_type"):
        draft_email("reminder", MEETING_TITLE, MEETING_DATE, ORGANIZER, ASSIGNED_ITEM, client=mock_client)
    mock_client.messages.create.assert_not_called()


def test_draft_email_parses_json_response():
    mock_client = _make_mock_client(json.dumps(EXPECTED_EMAIL))

    result = draft_email("assignment", MEETING_TITLE, MEETING_DATE, ORGANIZER, ASSIGNED_ITEM, client=mock_client)

    assert result == EXPECTED_EMAIL
    mock_client.messages.create.assert_called_once()


def test_draft_email_strips_markdown_fences():
    fenced = "```json\n" + json.dumps(EXPECTED_EMAIL) + "\n```"
    mock_client = _make_mock_client(fenced)

    result = draft_email("followup", MEETING_TITLE, MEETING_DATE, ORGANIZER, ASSIGNED_ITEM, client=mock_client)

    assert result == EXPECTED_EMAIL


def test_draft_email_passes_context_to_model():
    mock_client = _make_mock_client(json.dumps(EXPECTED_EMAIL))

    draft_email("assignment", MEETING_TITLE, MEETING_DATE, ORGANIZER, ASSIGNED_ITEM, client=mock_client)

    _, kwargs = mock_client.messages.create.call_args
    user_message = kwargs["messages"][0]["content"]
    assert MEETING_TITLE in user_message
    assert ORGANIZER in user_message
    assert "Marcus Webb" in user_message
    assert ASSIGNED_ITEM["description"] in user_message


def test_draft_email_batch_rejects_missing_owner():
    mock_client = _make_mock_client(json.dumps(EXPECTED_EMAIL))
    with pytest.raises(ValueError, match="no owner"):
        draft_email_batch("assignment", MEETING_TITLE, MEETING_DATE, ORGANIZER, None, [ASSIGNED_ITEM], client=mock_client)
    mock_client.messages.create.assert_not_called()


def test_draft_email_batch_rejects_empty_items():
    mock_client = _make_mock_client(json.dumps(EXPECTED_EMAIL))
    with pytest.raises(ValueError, match="non-empty list"):
        draft_email_batch("assignment", MEETING_TITLE, MEETING_DATE, ORGANIZER, "Marcus Webb", [], client=mock_client)
    mock_client.messages.create.assert_not_called()


def test_draft_email_batch_combines_multiple_items():
    mock_client = _make_mock_client(json.dumps(EXPECTED_EMAIL))
    second_item = {
        "description": "Schedule the vendor kickoff call",
        "owner": "Marcus Webb",
        "due_date": "2026-09-15",
        "status": "in_progress",
    }

    result = draft_email_batch(
        "assignment", MEETING_TITLE, MEETING_DATE, ORGANIZER, "Marcus Webb",
        [ASSIGNED_ITEM, second_item], client=mock_client,
    )

    assert result == EXPECTED_EMAIL
    _, kwargs = mock_client.messages.create.call_args
    user_message = kwargs["messages"][0]["content"]
    assert "Action items (2)" in user_message
    assert ASSIGNED_ITEM["description"] in user_message
    assert second_item["description"] in user_message
    assert "Marcus Webb" in user_message


def test_validate_email_rejects_empty_subject():
    with pytest.raises(ValueError, match="subject"):
        _validate_email({"subject": "", "body": "some body"})


def test_validate_email_rejects_missing_body():
    with pytest.raises(ValueError, match="body"):
        _validate_email({"subject": "some subject"})


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
