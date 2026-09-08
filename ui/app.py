"""Flask backend for the Meeting Notes Dashboard.

Bridges Ryan's dashboard UI with Leland's extraction agent, email draft
agent, and the SQLite storage layer.

Run:
    cd ui
    pip install -r requirements.txt
    ANTHROPIC_API_KEY=sk-... python app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make sibling packages importable without installing them
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "extraction-agent"))
sys.path.insert(0, str(ROOT / "storage"))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from agent import extract_action_items
from email_agent import draft_email
from storage import Storage

app = Flask(__name__, static_folder=str(Path(__file__).parent), static_url_path="")
CORS(app)

DB_PATH = ROOT / "storage" / "command_center.db"
_storage = Storage(DB_PATH)


# ── Serve the dashboard ───────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "dashboard.html")


# ── Extract ───────────────────────────────────────────────────────────────────

@app.route("/api/extract", methods=["POST"])
def api_extract():
    body = request.get_json(force=True)
    transcript = (body.get("transcript") or "").strip()
    if not transcript:
        return jsonify({"error": "transcript is required"}), 400

    meeting_title = body.get("meeting_title") or None
    meeting_date = body.get("meeting_date") or None
    organizer = body.get("organizer") or None

    try:
        extraction = extract_action_items(
            transcript,
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            organizer=organizer,
        )
    except Exception as exc:
        return jsonify({"error": f"Extraction failed: {exc}"}), 500

    try:
        meeting_id = _storage.save_extraction_result(extraction, organizer=organizer)
    except Exception as exc:
        return jsonify({"error": f"Storage failed: {exc}"}), 500

    meeting = _storage.get_meeting_with_items(meeting_id)
    return jsonify(meeting), 201


# ── Meetings ──────────────────────────────────────────────────────────────────

@app.route("/api/meetings", methods=["GET"])
def api_list_meetings():
    meetings = _storage.get_meetings()
    return jsonify([m.to_dict() for m in meetings])


@app.route("/api/meetings/<meeting_id>", methods=["GET"])
def api_get_meeting(meeting_id: str):
    meeting = _storage.get_meeting_with_items(meeting_id)
    if meeting is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(meeting)


# ── Action items ──────────────────────────────────────────────────────────────

@app.route("/api/action-items/<item_id>", methods=["PATCH"])
def api_update_action_item(item_id: str):
    body = request.get_json(force=True)
    status = body.get("status")
    note = body.get("note") or None
    if not status:
        return jsonify({"error": "status is required"}), 400
    try:
        _storage.update_status(item_id, status, note=note)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})


# ── Email drafts ──────────────────────────────────────────────────────────────

@app.route("/api/draft-email", methods=["POST"])
def api_draft_email():
    body = request.get_json(force=True)
    meeting_id = body.get("meeting_id")
    action_item_id = body.get("action_item_id")
    email_type = body.get("email_type", "assignment")

    if not meeting_id or not action_item_id:
        return jsonify({"error": "meeting_id and action_item_id are required"}), 400

    meeting = _storage.get_meeting_with_items(meeting_id)
    if meeting is None:
        return jsonify({"error": "Meeting not found"}), 404

    action_item = next(
        (a for a in meeting["action_items"] if a["id"] == action_item_id), None
    )
    if action_item is None:
        return jsonify({"error": "Action item not found"}), 404

    if not action_item.get("owner"):
        return jsonify({"error": "This action item has no owner — cannot draft an email without a recipient."}), 422

    try:
        draft = draft_email(
            email_type=email_type,
            meeting_title=meeting["meeting_title"],
            meeting_date=meeting.get("meeting_date"),
            organizer=meeting.get("organizer") or "the meeting organizer",
            action_item=action_item,
        )
    except Exception as exc:
        return jsonify({"error": f"Email draft failed: {exc}"}), 500

    return jsonify(draft)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
