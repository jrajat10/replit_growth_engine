"""
Funnel module — multi-stage conversion + quality-adjusted CAC + Free->Paid forecast.

Stages (Replit 2026 funnel):
    visits -> prompt_starts -> signups -> activated_first_app -> paid_conversions

The allocator continues to optimize on net-new signups (short-loop) — funnel data
exposes WHERE quality dies and feeds qCAC + forecast for leadership view.

DOES NOT replace LTV multipliers in v0. That upgrade lands in v1.5.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import config

# Definitional anchors — keep documented; defend in interview
ACTIVATION_DEFINITION = (
    "Activated = signup that publishes a first deployed app within 7 days. "
    "Not just 'Agent created something' -- too noisy."
)
QCAC_DEFINITION = (
    "qCAC = spend / paid_conversions (4-week trailing cohort). "
    "Standard CAC = spend / signups. Showing both makes quality gap visible."
)
PAID_LAG_WEEKS = 4  # typical Free->Paid lag for Replit Core/Pro


def _agg_week(rows: list[dict], segment: str, week_start: str) -> dict:
    agg = {"visits": 0, "prompt_starts": 0, "signups": 0.0,
           "activated_first_app": 0.0, "paid_conversions": 0.0}
    for r in rows:
        if r["segment"] != segment or r["week_start"] != week_start:
            continue
        for k in agg:
            agg[k] += r[k]
    return agg


def _agg_by_channel(rows: list[dict], segment: str, week_start: str) -> dict:
    by_ch: dict[str, dict] = defaultdict(
        lambda: {"visits": 0, "prompt_starts": 0, "signups": 0.0,
                 "activated_first_app": 0.0, "paid_conversions": 0.0}
    )
    for r in rows:
        if r["segment"] != segment or r["week_start"] != week_start:
            continue
        for k in by_ch[r["channel"]]:
            by_ch[r["channel"]][k] += r[k]
    return dict(by_ch)


def funnel_overview(
    funnel_rows: list[dict],
    perf_rows: list[dict],
    segment: str,
    week_start: str,
) -> dict[str, Any]:
    """Aggregate funnel for the week with stage-by-stage rates + qCAC."""
    cur = _agg_week(funnel_rows, segment, week_start)
    spend = sum(float(r["spend"]) for r in perf_rows
                if r["segment"] == segment and r["week_start"] == week_start)

    def rate(num, denom):
        return num / denom if denom else 0

    cac = spend / cur["signups"] if cur["signups"] else 0
    qcac = spend / cur["paid_conversions"] if cur["paid_conversions"] else 0

    stages = [
        {"stage": "Visits", "value": cur["visits"], "rate_from_prior": None},
        {"stage": "Prompt Starts", "value": cur["prompt_starts"],
         "rate_from_prior": rate(cur["prompt_starts"], cur["visits"])},
        {"stage": "Signups", "value": round(cur["signups"]),
         "rate_from_prior": rate(cur["signups"], cur["prompt_starts"])},
        {"stage": "Activated (first app, 7d)", "value": round(cur["activated_first_app"]),
         "rate_from_prior": rate(cur["activated_first_app"], cur["signups"])},
        {"stage": "Paid", "value": round(cur["paid_conversions"], 1),
         "rate_from_prior": rate(cur["paid_conversions"], cur["activated_first_app"])},
    ]

    return {
        "segment": segment,
        "week_start": week_start,
        "spend": round(spend),
        "stages": stages,
        "cac": round(cac, 2),
        "qcac": round(qcac, 2),
        "qcac_to_cac_ratio": round(qcac / cac, 1) if cac else 0,
        "activation_rate": round(rate(cur["activated_first_app"], cur["signups"]) * 100, 1),
        "free_to_paid_rate": round(rate(cur["paid_conversions"], cur["activated_first_app"]) * 100, 2),
        "prompt_start_rate": round(rate(cur["prompt_starts"], cur["visits"]) * 100, 1),
        "definitions": {
            "activation": ACTIVATION_DEFINITION,
            "qcac": QCAC_DEFINITION,
        },
    }


def channel_funnel_table(
    funnel_rows: list[dict],
    perf_rows: list[dict],
    segment: str,
    week_start: str,
) -> list[dict]:
    """Per-channel CAC vs qCAC, activation rate, Free->Paid rate."""
    by_ch = _agg_by_channel(funnel_rows, segment, week_start)
    spend_by_ch: dict[str, float] = defaultdict(float)
    for r in perf_rows:
        if r["segment"] == segment and r["week_start"] == week_start:
            spend_by_ch[r["channel"]] += float(r["spend"])

    rows = []
    for ch in config.CHANNELS.get(segment, []):
        d = by_ch.get(ch, {"visits": 0, "prompt_starts": 0, "signups": 0.0,
                            "activated_first_app": 0.0, "paid_conversions": 0.0})
        spend = spend_by_ch.get(ch, 0)
        cac = spend / d["signups"] if d["signups"] else 0
        qcac = spend / d["paid_conversions"] if d["paid_conversions"] else 0
        act_rate = (d["activated_first_app"] / d["signups"]) if d["signups"] else 0
        f2p = (d["paid_conversions"] / d["activated_first_app"]) if d["activated_first_app"] else 0
        rows.append({
            "channel": ch,
            "label": config.CHANNEL_LABELS.get(ch, ch),
            "spend": round(spend),
            "signups": round(d["signups"]),
            "activated": round(d["activated_first_app"]),
            "paid": round(d["paid_conversions"], 1),
            "cac": round(cac, 2),
            "qcac": round(qcac, 2),
            "activation_rate_pct": round(act_rate * 100, 1),
            "free_to_paid_pct": round(f2p * 100, 2),
            "quality_flag": _quality_flag(cac, qcac, act_rate),
        })
    return sorted(rows, key=lambda r: -r["spend"])


def _quality_flag(cac: float, qcac: float, act_rate: float) -> str:
    if cac == 0:
        return ""
    if qcac > 0 and qcac > cac * 20:
        return "low_paid_quality"
    if act_rate < 0.30:
        return "low_activation"
    return ""


def forecast_free_to_paid(
    funnel_rows: list[dict],
    segment: str,
    week_start: str,
    all_weeks: list[str],
) -> dict[str, Any]:
    """
    Simple forecast: activated_this_week x measured paid_rate from prior 4-week cohort.

    Why this exists: paid_conversions lags 4+ weeks. Allocator can't optimize on it
    directly. Forecast = short-loop activation signal projected forward using
    measured cohort rates -> blended signal for next-week call.
    """
    weeks_sorted = sorted(all_weeks)
    if week_start not in weeks_sorted:
        return {"available": False}
    idx = weeks_sorted.index(week_start)
    cohort_weeks = weeks_sorted[max(0, idx - PAID_LAG_WEEKS):idx]
    if not cohort_weeks:
        return {"available": False}

    by_ch_cohort: dict[str, dict] = defaultdict(lambda: {"act": 0.0, "paid": 0.0})
    for r in funnel_rows:
        if r["segment"] == segment and r["week_start"] in cohort_weeks:
            by_ch_cohort[r["channel"]]["act"] += r["activated_first_app"]
            by_ch_cohort[r["channel"]]["paid"] += r["paid_conversions"]

    rates = {ch: (v["paid"] / v["act"] if v["act"] else 0) for ch, v in by_ch_cohort.items()}

    cur_by_ch = _agg_by_channel(funnel_rows, segment, week_start)
    forecast_rows = []
    total = 0.0
    for ch, d in cur_by_ch.items():
        rate = rates.get(ch, 0)
        proj = d["activated_first_app"] * rate
        total += proj
        forecast_rows.append({
            "channel": ch,
            "label": config.CHANNEL_LABELS.get(ch, ch),
            "activated_this_week": round(d["activated_first_app"]),
            "cohort_paid_rate_pct": round(rate * 100, 2),
            "forecast_paid": round(proj, 1),
        })

    return {
        "available": True,
        "cohort_weeks": cohort_weeks,
        "lag_weeks": PAID_LAG_WEEKS,
        "method": "activated_this_week x measured paid_rate from prior 4-week cohort",
        "rows": sorted(forecast_rows, key=lambda r: -r["forecast_paid"]),
        "total_forecast_paid": round(total, 1),
        "note": (
            "Short-loop signal for speed; long-loop ground truth calibrates the rate. "
            "We don't wait 4 weeks to make this week's call."
        ),
    }


def time_to_first_app_distribution(funnel_rows: list[dict], segment: str, week_start: str) -> dict:
    """
    v0 placeholder: we don't have per-user timestamps in sample data.
    Surface as a known gap that v1 will fill from sessions table.
    """
    return {
        "available": False,
        "note": (
            "Time-to-First-App (p50/p90) requires per-user event timestamps. "
            "Sample data is week-grain only. v1 plugs into fct_user_events."
        ),
    }
