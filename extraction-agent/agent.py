"""Extraction agent: pulls structured action items out of a meeting transcript
using the Claude API.

See ../requirements.md for the data model and extraction rules, and
prompts.md for the system prompt this agent sends to Claude.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-5"

PROMPTS_PATH = Path(__file__).parent / "prompts.md"


def load_system_prompt() -> str:
    """Pull the system prompt out of the fenced code block in prompts.md."""
    text = PROMPTS_PATH.read_text()
    match = re.search(r"## System Prompt\s*```\n(.*?)\n```", text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find system prompt block in {PROMPTS_PATH}")
    return match.group(1).strip()


def _parse_json_response(text: str) -> dict:
    """Claude is asked to return raw JSON, but strip fences defensively in
    case it wraps the response in ```json ... ``` anyway."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def extract_action_items(
    transcript: str,
    meeting_title: str | None = None,
    meeting_date: str | None = None,
    organizer: str | None = None,
    client: anthropic.Anthropic | None = None,
    model: str = MODEL,
) -> dict:
    """Run the extraction agent over a transcript and return a dict matching
    the schema in requirements.md:

    {
      "meeting_title": str | None,
      "meeting_date": str | None,
      "action_items": [
        {"description": str, "owner": str | None,
         "due_date": str | None, "status": str},
        ...
      ]
    }
    """
    client = client or anthropic.Anthropic()

    known_fields = []
    if meeting_title:
        known_fields.append(f"Meeting title: {meeting_title}")
    if meeting_date:
        known_fields.append(f"Meeting date: {meeting_date}")
    if organizer:
        known_fields.append(f"Meeting organizer: {organizer}")
    known_fields_block = "\n".join(known_fields)

    user_message = (
        f"{known_fields_block}\n\n" if known_fields_block else ""
    ) + f"Transcript:\n{transcript}"

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=load_system_prompt(),
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    return _parse_json_response(response_text)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python agent.py <transcript_path>")
        sys.exit(1)

    transcript_text = Path(sys.argv[1]).read_text()
    result = extract_action_items(transcript_text)
    print(json.dumps(result, indent=2))
