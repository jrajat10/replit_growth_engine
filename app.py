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


def _float_or_none(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _rate(v):
    """Tolerate either 0.045 or 4.5 for percentage inputs."""
    f = _float_or_none(v)
    if f is None:
        return None
    return f / 100 if f > 1 else f


@app.route("/api/state")
def api_state():
    segment = request.args.get("segment", "consumer")
    if segment not in ("consumer", "enterprise"):
        segment = "consumer"
    f2p = _rate(request.args.get("free_to_paid"))
    activation = _rate(request.args.get("activation"))
    arr_target = _float_or_none(request.args.get("arr_target"))
    ingest.sync_from_source()
    state = ingest.get_state(segment, f2p, activation, arr_target)
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


@app.route("/api/pacing/stage_shift", methods=["POST"])
def api_stage_pacing_shift():
    """Closed-loop: stage the pacing-corrected allocator shift as a pending decision."""
    data = request.get_json() or {}
    segment = data.get("segment", "consumer")
    action = data.get("action", "staged")
    state = ingest.get_state(segment)
    pacing = state.get("pacing", {})
    cr = pacing.get("corrective_recommendation")
    if not cr:
        return jsonify({"ok": False, "error": "No corrective recommendation available"}), 400

    record = knowledge.append({
        "type": "pacing_corrective_shift",
        "segment": segment,
        "week_start": state["week_start"],
        "quarter_label": pacing.get("quarter_label"),
        "current_week_idx": pacing.get("current_week_idx"),
        "weeks_remaining": pacing.get("weeks_remaining"),
        "total_shift_per_week": cr["total_shift_per_week"],
        "shifts": cr["shifts"],
        "cap_hit": cr["cap_hit"],
        "summary": cr["headline"],
        "human_action": action,
        "note": (
            f"Staged pacing-corrected shift to close Q-end gap. "
            f"Pairs with the math-optimal allocation on Monday review for side-by-side approval."
        ),
    })
    return jsonify({"ok": True, "record": record})


@app.route("/api/trends")
def api_trends():
    segment = request.args.get("segment", "consumer")
    if segment not in ("consumer", "enterprise"):
        segment = "consumer"
    return jsonify(ingest.get_trends(segment))
