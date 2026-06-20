"""
Data Science model integration layer.

The growth app CONSUMES model outputs — it does not train models.
DS team owns training, validation, and publishing scores to the warehouse.

Contract: data/sample/ml_channel_scores.csv (sample) or warehouse table
  ml_channel_scores in production (see MODEL_CONTRACT below).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

SAMPLE_MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "sample" / "ml_channel_scores.csv"

MODEL_CONTRACT = {
    "table": "ml_channel_scores",
    "owner": "Data Science",
    "grain": "weekly × segment × channel",
    "refresh": "weekly (after warehouse close)",
    "fields": {
        "week_start": "Monday of scoring week (aligns with fct_paid_performance)",
        "segment": "consumer | enterprise",
        "channel": "channel key (matches config.CHANNELS)",
        "predicted_net_new_per_dollar": "DS model: expected net-new conversions per $1 spend",
        "predicted_ltv": "DS model: expected LTV per net-new conversion",
        "efficiency_score": "Combined score used by allocator (DS-defined)",
        "confidence": "0-1 model confidence; allocator down-weights if < 0.5",
        "model_version": "e.g. channel_efficiency_v2.1",
        "scored_at": "ISO timestamp of batch scoring run",
    },
    "integration": (
        "Growth app reads scores in engine/models.py. "
        "If scores exist for the active week, allocation uses DS efficiency_score "
        "instead of the heuristic (net-new/$ × LTV multiplier). "
        "If missing, falls back to heuristic and surfaces a banner."
    ),
}


def load_channel_scores(week_start: str, segment: str) -> dict[str, Any]:
    """
    Load DS-published channel scores for a week/segment.
    Returns {channel: score_row, ...} or empty dict if unavailable.
    """
    if not SAMPLE_MODEL_PATH.exists():
        return {"available": False, "scores": {}, "source": "none"}

    rows = []
    with SAMPLE_MODEL_PATH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["week_start"] == week_start and r["segment"] == segment:
                rows.append(r)

    if not rows:
        return {"available": False, "scores": {}, "source": "none"}

    scores = {}
    for r in rows:
        scores[r["channel"]] = {
            "predicted_net_new_per_dollar": float(r["predicted_net_new_per_dollar"]),
            "predicted_ltv": float(r["predicted_ltv"]),
            "efficiency_score": float(r["efficiency_score"]),
            "confidence": float(r["confidence"]),
            "model_version": r["model_version"],
        }

    version = rows[0]["model_version"] if rows else "unknown"
    return {
        "available": True,
        "scores": scores,
        "model_version": version,
        "source": "ml_channel_scores (DS team)",
        "scored_at": rows[0].get("scored_at", ""),
    }


def apply_to_allocation_scores(
    heuristic_scores: dict[str, float],
    model_output: dict[str, Any],
    min_confidence: float = 0.5,
) -> tuple[dict[str, float], dict[str, str]]:
    """
    Blend DS scores into allocation when model is available.
    Low-confidence channels keep heuristic score.
    Returns (final_scores, explanations_per_channel).
    """
    if not model_output.get("available"):
        return heuristic_scores, {
            ch: "Heuristic (DS model not available for this week)"
            for ch in heuristic_scores
        }

    ds_scores = model_output["scores"]
    final = {}
    explanations = {}
    version = model_output.get("model_version", "DS")

    for ch, h_score in heuristic_scores.items():
        ds = ds_scores.get(ch)
        if ds and ds["confidence"] >= min_confidence:
            final[ch] = ds["efficiency_score"]
            explanations[ch] = (
                f"DS model {version} (confidence {ds['confidence']:.0%}): "
                f"efficiency={ds['efficiency_score']:.4f}"
            )
        else:
            final[ch] = h_score
            conf = ds["confidence"] if ds else 0
            explanations[ch] = (
                f"Heuristic fallback"
                + (f" (DS confidence {conf:.0%} below {min_confidence:.0%})" if ds else "")
            )

    return final, explanations
