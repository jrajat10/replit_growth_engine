"""
Competition module — alert explainer, not a dashboard.

Discipline:
  - Only surfaces a competitor signal when it explains an existing alert.
  - Every signal carries confidence + source.
  - Goal: change allocator posture from FIX -> DEFEND when CAC inflation is
    market-driven, not funnel-driven.

DOES NOT compute a global "threat index" in v0. That belongs in v2 once we
have continuous signal sources, not hand-authored captures.
"""

from __future__ import annotations

from typing import Any


def explain_alert(
    alert: dict,
    competitors: list[dict],
    signals: list[dict],
    week_start: str,
) -> dict | None:
    """
    Find a competitor signal in the same week+channel as the alert that could
    explain it. Returns None if no plausible attribution.
    """
    if alert.get("type") not in ("cac_shift", "creative_fatigue"):
        # Geo and other narrow alerts shouldn't grab market-wide signals.
        return None

    msg = (alert.get("message") or "").lower()
    title = (alert.get("title") or "").lower()
    channel_hint = None
    for hint in ("google", "meta", "tiktok", "linkedin", "youtube", "reddit"):
        if hint in msg or hint in title:
            channel_hint = hint
            break

    # Require a channel match. cac_shift without channel hint = aggregate move;
    # only surface a competitor if their signal also affects multiple channels
    # (signal_type == "funding_signal" is broad; others are channel-specific).
    if channel_hint:
        relevant = [
            s for s in signals
            if s.get("week_start") == week_start
            and channel_hint in s.get("channel", "")
        ]
    else:
        relevant = [
            s for s in signals
            if s.get("week_start") == week_start
            and s.get("signal_type") == "funding_signal"
        ]
    if not relevant:
        return None

    # Prefer highest-confidence matching signal
    relevant.sort(key=lambda s: s.get("confidence", 0), reverse=True)
    s = relevant[0]
    comp = next((c for c in competitors if c["competitor_id"] == s["competitor_id"]), None)

    posture = "defend" if alert.get("type") == "cac_shift" else "investigate"
    return {
        "signal_id": s["signal_id"],
        "competitor": comp["name"] if comp else s["competitor_id"],
        "channel": s.get("channel", ""),
        "signal_type": s.get("signal_type", ""),
        "value": s.get("value", ""),
        "confidence": s.get("confidence", 0),
        "source": s.get("source", ""),
        "interpretation": s.get("interpretation", ""),
        "implication": s.get("implication", ""),
        "posture_recommendation": posture,
        "explanation": (
            f"{alert.get('title')} likely explained by: "
            f"{comp['name'] if comp else s['competitor_id']} {s.get('signal_type','')} "
            f"({s.get('value','')}). {s.get('implication','')}"
        ),
        "framing": (
            "Posture: DEFEND. CAC inflation looks market-driven — hold spend, "
            "don't burn creative budget chasing a market move."
            if posture == "defend"
            else "Investigate cross-channel impact."
        ),
    }


def attach_explanations(
    alerts: list[dict],
    competitors: list[dict],
    signals: list[dict],
    week_start: str,
) -> list[dict]:
    """Mutates alerts in place, adding a competitor_context where applicable."""
    for a in alerts:
        ctx = explain_alert(a, competitors, signals, week_start)
        if ctx:
            a["competitor_context"] = ctx
    return alerts


def landscape_snapshot(competitors: list[dict], signals: list[dict]) -> dict:
    """Compact view for the cockpit — list competitors + most recent signals."""
    sigs = sorted(signals, key=lambda s: (s.get("week_start", ""), s.get("confidence", 0)), reverse=True)
    return {
        "competitors": competitors,
        "recent_signals": sigs[:5],
        "discipline_note": (
            "Competitive data only surfaces when it explains a decision. "
            "Confidence + source labels make provenance auditable."
        ),
        "sources_in_use": sorted({s.get("source", "") for s in signals if s.get("source")}),
    }
