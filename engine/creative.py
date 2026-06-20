"""Creative testing — fatigue detection and Brand insight cards (no copy generation)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import config


def _fatigue_score(weekly: list[dict]) -> tuple[str, float, str]:
    """Compare recent 2 weeks CTR trend vs prior 2 weeks."""
    if len(weekly) < 4:
        return "low", 0.0, "Insufficient history"
    weekly = sorted(weekly, key=lambda x: x["week_start"])
    def ctr(rows):
        imp = sum(r["impressions"] for r in rows)
        clk = sum(r["clicks"] for r in rows)
        return clk / imp if imp else 0
    recent = ctr(weekly[-2:])
    prior = ctr(weekly[-4:-2])
    if prior == 0:
        return "low", 0.0, "No baseline"
    drop = (prior - recent) / prior
    if drop > 0.25:
        return "high", drop, f"CTR down {drop*100:.0f}% over last 2 weeks vs prior 2"
    if drop > 0.12:
        return "medium", drop, f"CTR softening ({drop*100:.0f}% decline)"
    return "low", drop, "Performance stable"


def build_insight_cards(
    creatives: list[dict],
    perf: list[dict],
    segment: str,
    latest_week: str,
) -> list[dict]:
    """Brand handoff artifacts — what we learned, not what we said."""
    by_cr: dict[str, list] = defaultdict(list)
    for r in perf:
        by_cr[r["creative_id"]].append(r)

    cards = []
    for cr in creatives:
        if cr["segment"] != segment:
            continue
        rows = by_cr.get(cr["creative_id"], [])
        fatigue, drop, fatigue_msg = _fatigue_score(rows)
        latest = next((r for r in rows if r["week_start"] == latest_week), None)
        imp = latest["impressions"] if latest else 0
        conv = float(latest["conversions"]) if latest else 0

        directive = config.BRAND_DIRECTIVES.get(cr["brand_directive"], cr["brand_directive"])
        recommendation = "Continue testing"
        if fatigue == "high":
            recommendation = f"Rotate — fatigue detected. Test alternative per directive: {directive}"
        elif fatigue == "medium":
            recommendation = "Monitor closely; prepare backup variant"

        cards.append({
            "creative_id": cr["creative_id"],
            "name": cr["name"],
            "channel": cr["channel"],
            "channel_label": config.CHANNEL_LABELS.get(cr["channel"], cr["channel"]),
            "brand_directive": cr["brand_directive"],
            "directive_text": directive,
            "fatigue": fatigue,
            "fatigue_drop_pct": round(drop * 100, 1),
            "fatigue_message": fatigue_msg,
            "latest_impressions": imp,
            "latest_conversions": round(conv, 1),
            "insight_summary": (
                f"{cr['name']}: {fatigue_msg}. "
                f"Brand directive tested: '{directive}'. "
                f"Recommendation: {recommendation}"
            ),
            "finding": fatigue_msg,
            "hypothesis": (
                "Income-claim hook may be stale with target audience"
                if "income" in cr["name"].lower() and fatigue == "high"
                else "Creative performing within expected range"
            ),
            "recommend_to_brand": recommendation,
            "status": cr["status"],
            "handoff_note": "Insight card for Brand — we test directives; Brand owns copy.",
        })
    return sorted(cards, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["fatigue"]])
