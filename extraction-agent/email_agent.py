"""Email draft agent: generates organizer-voiced draft emails for action items.

DRAFT ONLY. Per requirements.md ("Email Draft Generation Specification"),
this phase never sends email — Outlook/SMTP integration is explicitly out
of scope until the send pipeline is wired and tested separately. This is
also the exact feature that broke Hepsi's original build (a half-configured
send-email path tied to an unconfigured API key), so this module has no
send capability at all, only draft generation. The output here is content
for a human to review and send themselves.

See ../requirements.md for the rules and email_prompts.md for the system
prompt this agent sends to Claude.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

import anthropic

MODEL = "claude-sonnet-5"

EMAIL_PROMPTS_PATH = Path(__file__).parent / "email_prompts.md"

EmailType = Literal["assignment", "followup"]
VALID_EMAIL_TYPES = {"assignment", "followup"}


def load_email_system_prompt() -> str:
    """Pull the system prompt out of the fenced code block in email_prompts.md."""
    text = EMAIL_PROMPTS_PATH.read_text()
    match = re.search(r"## System Prompt\s*```\n(.*?)\n```", text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find system prompt block in {EMAIL_PROMPTS_PATH}")
    return match.group(1).strip()


def _parse_json_response(text: str) -> dict:
    """Claude is asked to return raw JSON, but strip fences defensively in
    case it wraps the response in ```json ... ``` anyway."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _validate_email(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")
    for key in ("subject", "body"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
    return data


def draft_email(
    email_type: EmailType,
    meeting_title: str,
    meeting_date: str | None,
    organizer: str,
    action_item: dict,
    client: anthropic.Anthropic | None = None,
    model: str = MODEL,
) -> dict:
    """Draft a single organizer-voiced email for one action item.

    action_item must match agent.py's output schema (description, owner,
    due_date, status). owner must not be None/empty — there is no one to
    address the email to for an unassigned action item, and this function
    will not guess a recipient.

    Thin wrapper around draft_email_batch for a single-item list.

    Returns {"subject": str, "body": str}. Does not send anything.
    """
    owner = action_item.get("owner")
    return draft_email_batch(
        email_type, meeting_title, meeting_date, organizer, owner, [action_item],
        client=client, model=model,
    )


def draft_email_batch(
    email_type: EmailType,
    meeting_title: str,
    meeting_date: str | None,
    organizer: str,
    owner: str | None,
    action_items: list[dict],
    client: anthropic.Anthropic | None = None,
    model: str = MODEL,
) -> dict:
    """Draft one organizer-voiced email covering one or more action items
    for a single owner.

    Each item in action_items must match agent.py's output schema
    (description, owner, due_date, status). owner must not be None/empty —
    there is no one to address the email to, and this function will not
    guess a recipient. Callers are responsible for grouping items by owner
    before calling this — it does not check that every item's own "owner"
    field matches the owner argument.

    Returns {"subject": str, "body": str}. Does not send anything.
    """
    if email_type not in VALID_EMAIL_TYPES:
        raise ValueError(f"email_type must be one of {sorted(VALID_EMAIL_TYPES)}, got {email_type!r}")

    if not owner:
        raise ValueError("Cannot draft an email for an action item with no owner")

    if not action_items:
        raise ValueError("action_items must be a non-empty list")

    for item in action_items:
        if not item.get("description"):
            raise ValueError("action_item.description is required")

    client = client or anthropic.Anthropic()

    if len(action_items) == 1:
        item = action_items[0]
        items_text = (
            f"Action item description: {item['description']}\n"
            f"Due date: {item.get('due_date') or 'not specified'}\n"
            f"Status: {item.get('status', 'in_progress')}"
        )
    else:
        items_text = f"Action items ({len(action_items)}):\n" + "\n".join(
            f"{i}. {item['description']} (due: {item.get('due_date') or 'not specified'}, "
            f"status: {item.get('status', 'in_progress')})"
            for i, item in enumerate(action_items, start=1)
        )

    user_message = (
        f"Email type: {email_type}\n"
        f"Meeting title: {meeting_title}\n"
        f"Meeting date: {meeting_date or 'not specified'}\n"
        f"Organizer: {organizer}\n"
        f"Owner: {owner}\n"
        f"{items_text}\n"
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=load_email_system_prompt(),
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    return _validate_email(_parse_json_response(response_text))
