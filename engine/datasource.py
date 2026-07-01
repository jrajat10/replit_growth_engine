"""Warehouse connector — reads sample CSV fixtures today; swap SQL for production."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"


def _read_csv(name: str) -> list[dict[str, Any]]:
    path = SAMPLE_DIR / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_paid_performance() -> list[dict]:
    rows = _read_csv("fct_paid_performance.csv")
    for r in rows:
        r["spend"] = float(r["spend"])
        r["impressions"] = int(float(r["impressions"]))
        r["clicks"] = int(float(r["clicks"]))
        r["conversions"] = float(r["conversions"])
        r["new_user_conversions"] = float(r["new_user_conversions"])
        r["returning_user_conversions"] = float(r["returning_user_conversions"])
        if r.get("conversion_value"):
            r["conversion_value"] = float(r["conversion_value"])
    return rows


def load_conversion_paths() -> list[dict]:
    return _read_csv("fct_conversion_paths.csv")


def load_experiments() -> list[dict]:
    return _read_csv("dim_experiments.csv")


def load_experiment_results() -> list[dict]:
    rows = _read_csv("fct_experiment_results.csv")
    for r in rows:
        for k in ("control_conversions", "variant_conversions", "control_n", "variant_n"):
            r[k] = float(r[k])
    return rows


def load_creatives() -> list[dict]:
    return _read_csv("dim_creative.csv")


def load_creative_performance() -> list[dict]:
    rows = _read_csv("fct_creative_performance.csv")
    for r in rows:
        r["impressions"] = int(float(r["impressions"]))
        r["clicks"] = int(float(r["clicks"]))
        r["conversions"] = float(r["conversions"])
    return rows


def load_funnel_events() -> list[dict]:
    rows = _read_csv("fct_funnel_events.csv")
    for r in rows:
        r["visits"] = int(float(r["visits"]))
        r["prompt_starts"] = int(float(r["prompt_starts"]))
        r["signups"] = float(r["signups"])
        r["activated_first_app"] = float(r["activated_first_app"])
        r["paid_conversions"] = float(r["paid_conversions"])
    return rows


def load_competitors() -> list[dict]:
    return _read_csv("dim_competitor.csv")


def load_competitor_signals() -> list[dict]:
    rows = _read_csv("fct_competitor_signals.csv")
    for r in rows:
        r["confidence"] = float(r["confidence"])
    return rows


def load_keyword_overlap() -> list[dict]:
    rows = _read_csv("fct_keyword_overlap.csv")
    for r in rows:
        r["impression_share"] = float(r["impression_share"])
        r["avg_cpc"] = float(r["avg_cpc"])
    return rows


def connection_status() -> dict:
    ok = (SAMPLE_DIR / "fct_paid_performance.csv").exists()
    return {
        "connected": ok,
        "mode": "SAMPLE",
        "label": "SAMPLE — not connected to live warehouse",
        "path": str(SAMPLE_DIR),
    }
