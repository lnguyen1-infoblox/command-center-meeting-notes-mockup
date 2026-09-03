"""Simple tests for the extraction agent. Mocks the Claude API call so tests
run without a network connection or API key.

Run with: pytest test_extraction.py
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from agent import extract_action_items, load_system_prompt

SAMPLE_TRANSCRIPT = """
[10:00] Alex: Let's kick off Q3 planning.
[10:05] Alex: Sarah, can you finalize the roadmap doc by next Friday, Sept 10th?
[10:05] Sarah: Sure, I'll have it done by then.
[10:10] Alex: We also need someone to review vendor proposals, but let's figure out who later.
"""

EXPECTED_RESPONSE = {
    "meeting_title": "Q3 Planning Session",
    "meeting_date": "2026-09-01",
    "action_items": [
        {
            "description": "Finalize the Q3 roadmap document",
            "owner": "Sarah Chen",
            "due_date": "2026-09-10",
            "status": "in_progress",
        },
        {
            "description": "Review vendor proposals for infrastructure upgrade",
            "owner": None,
            "due_date": None,
            "status": "in_progress",
        },
    ],
}


def _make_mock_client(response_text: str) -> MagicMock:
    mock_client = MagicMock()
    mock_client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=response_text)]
    )
    return mock_client


def test_load_system_prompt_contains_key_rules():
    prompt = load_system_prompt()
    assert "Never invent" in prompt
    assert "action_items" in prompt


def test_extract_action_items_parses_json_response():
    mock_client = _make_mock_client(json.dumps(EXPECTED_RESPONSE))

    result = extract_action_items(SAMPLE_TRANSCRIPT, client=mock_client)

    assert result == EXPECTED_RESPONSE
    mock_client.messages.create.assert_called_once()


def test_extract_action_items_strips_markdown_fences():
    fenced = "```json\n" + json.dumps(EXPECTED_RESPONSE) + "\n```"
    mock_client = _make_mock_client(fenced)

    result = extract_action_items(SAMPLE_TRANSCRIPT, client=mock_client)

    assert result == EXPECTED_RESPONSE


def test_extract_action_items_passes_known_fields_to_model():
    mock_client = _make_mock_client(json.dumps(EXPECTED_RESPONSE))

    extract_action_items(
        SAMPLE_TRANSCRIPT,
        meeting_title="Q3 Planning Session",
        meeting_date="2026-09-01",
        organizer="Alex",
        client=mock_client,
    )

    _, kwargs = mock_client.messages.create.call_args
    user_message = kwargs["messages"][0]["content"]
    assert "Q3 Planning Session" in user_message
    assert "2026-09-01" in user_message
    assert "Alex" in user_message


def test_extract_action_items_does_not_invent_owner_or_due_date():
    # Confirms the schema allows null owner/due_date and that they pass
    # through untouched rather than being coerced to a placeholder.
    mock_client = _make_mock_client(json.dumps(EXPECTED_RESPONSE))

    result = extract_action_items(SAMPLE_TRANSCRIPT, client=mock_client)

    unassigned_item = result["action_items"][1]
    assert unassigned_item["owner"] is None
    assert unassigned_item["due_date"] is None


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
