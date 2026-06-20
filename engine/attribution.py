"""Incrementality-first attribution — simple diagnostics, not a model zoo."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _parse_paths(paths: list[dict]) -> dict:
    """Last-touch vs first-touch credit for converted paths."""
    last_touch = defaultdict(float)
    first_touch = defaultdict(float)
    converted = 0
    for p in paths:
        if p.get("converted") not in ("1", 1, True):
            continue
        converted += 1
        touches = p["touch_sequence"].split(">")
        last_touch[touches[-1]] += 1
        first_touch[touches[0]] += 1
    return {
        "converted_paths": converted,
        "last_touch": dict(last_touch),
        "first_touch": dict(first_touch),
    }


def _markov_removal_effect(paths: list[dict]) -> dict[str, float]:
    """
    Simplified Markov removal effect: for each channel, estimate
    conversion rate drop if channel removed from paths.
    """
    channels = set()
    for p in paths:
        for t in p["touch_sequence"].split(">"):
            channels.add(t)

    def conv_rate(use_paths):
        if not use_paths:
            return 0
        return sum(1 for p in use_paths if p.get("converted") in ("1", 1, True)) / len(use_paths)

    base = conv_rate(paths)
    effects = {}
    for ch in channels:
        filtered = [
            p for p in paths
            if ch not in p["touch_sequence"].split(">")
        ]
        without = conv_rate(filtered) if filtered else 0
        effects[ch] = max(0, base - without)
    total = sum(effects.values()) or 1
    return {k: v / total for k, v in effects.items()}


def analyze(paths: list[dict], segment: str = "consumer") -> dict[str, Any]:
    seg_paths = [p for p in paths if p.get("segment", "consumer") == segment]
    if not seg_paths:
        return {"segment": segment, "message": "No path data"}

    parsed = _parse_paths(seg_paths)
    markov = _markov_removal_effect(seg_paths)
    lt = parsed["last_touch"]
    total_lt = sum(lt.values()) or 1

    # Key insight: retargeting over-credit
    retarget_share_lt = lt.get("meta_retarget", 0) / total_lt
    retarget_share_markov = markov.get("meta_retarget", 0)
    overcredit_pct = (
        (retarget_share_lt - retarget_share_markov) / retarget_share_markov * 100
        if retarget_share_markov > 0 else 0
    )

    return {
        "segment": segment,
        "headline": "Attribution shows direction — geo holdout proves causation",
        "simple_explanation": (
            "Last-touch says who got credit for the final click. "
            "Markov asks: if we removed this channel, how many conversions would we lose? "
            "When last-touch credits retargeting much more than Markov, "
            "retargeting is probably over-valued — that's why we run geo holdout tests."
        ),
        "last_touch_top": sorted(lt.items(), key=lambda x: -x[1])[:4],
        "markov_top": sorted(markov.items(), key=lambda x: -x[1])[:4],
        "retargeting_diagnostic": {
            "last_touch_share": round(retarget_share_lt * 100, 1),
            "markov_share": round(retarget_share_markov * 100, 1),
            "overcredit_estimate_pct": round(overcredit_pct, 1),
            "plain_english": (
                f"Last-touch gives Meta Retargeting {retarget_share_lt*100:.0f}% of credit, "
                f"but Markov suggests only {retarget_share_markov*100:.0f}% is truly incremental. "
                f"Don't cut prospecting based on last-touch alone."
            ),
        },
        "action": "Use geo holdout (Experiments tab) before shifting retargeting budget.",
    }
