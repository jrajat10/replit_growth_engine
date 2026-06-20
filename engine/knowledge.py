"""Append-only decision ledger — compounding institutional memory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

LEDGER_DIR = Path(__file__).resolve().parent.parent / "data" / "ledger"
LEDGER_FILE = LEDGER_DIR / "decisions.jsonl"


def _ensure():
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    if not LEDGER_FILE.exists():
        LEDGER_FILE.write_text("", encoding="utf-8")


def append(entry: dict[str, Any]) -> dict:
    _ensure()
    record = {
        "id": str(uuid4())[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **entry,
    }
    with LEDGER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def read_all(limit: int = 50) -> list[dict]:
    _ensure()
    lines = LEDGER_FILE.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(ln) for ln in lines if ln.strip()]
    return list(reversed(records[-limit:]))


def log_allocation_decision(
    segment: str,
    week_start: str,
    allocation: dict,
    human_action: str = "pending",
    note: str = "",
) -> dict:
    return append({
        "type": "allocation_recommendation",
        "segment": segment,
        "week_start": week_start,
        "recommended_allocation": allocation.get("allocation", {}),
        "summary": allocation.get("summary", ""),
        "human_action": human_action,
        "note": note,
    })


def log_experiment_learning(experiment: dict) -> dict | None:
    if not experiment.get("learning"):
        return None
    return append({
        "type": "experiment_learning",
        "experiment_id": experiment["experiment_id"],
        "name": experiment["name"],
        "learning": experiment["learning"],
        "recommendation": experiment.get("recommendation"),
    })


def approve_decision(decision_id: str, action: str = "approved", note: str = "") -> dict | None:
    records = read_all(200)
    for r in records:
        if r["id"] == decision_id:
            return append({
                "type": "human_action",
                "ref_id": decision_id,
                "action": action,
                "note": note,
            })
    return None
