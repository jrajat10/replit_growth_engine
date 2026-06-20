"""Flask application — landing + cockpit API."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from engine.decision_memo import build_memo
from engine import ingest, knowledge, nl_query

app = Flask(__name__)


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/cockpit")
def cockpit():
    return render_template("cockpit.html")


@app.route("/api/state")
def api_state():
    segment = request.args.get("segment", "consumer")
    if segment not in ("consumer", "enterprise"):
        segment = "consumer"
    ingest.sync_from_source()
    state = ingest.get_state(segment)
    memo = build_memo(state)
    return jsonify({"state": state, "memo": memo})


@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json() or {}
    question = data.get("question", "")
    segment = data.get("segment", "consumer")
    state = ingest.get_state(segment)
    memo = build_memo(state)
    result = nl_query.answer(question, state, memo)
    return jsonify(result)


@app.route("/api/approve", methods=["POST"])
def api_approve():
    data = request.get_json() or {}
    decision_id = data.get("decision_id", "alloc_main")
    segment = data.get("segment", "consumer")
    action = data.get("action", "approved")
    note = data.get("note", "")

    state = ingest.get_state(segment)
    alloc = state["allocation"]
    record = knowledge.log_allocation_decision(
        segment, state["week_start"], alloc, human_action=action, note=note or f"Approved via cockpit ({decision_id})"
    )
    return jsonify({"ok": True, "record": record})


@app.route("/api/sync", methods=["POST"])
def api_sync():
    weeks = ingest.sync_from_source()
    return jsonify({"ok": True, "weeks": len(weeks), "latest": weeks[-1] if weeks else None})
