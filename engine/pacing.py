"""
Pacing & quarterly targets — forward-looking view of the engine.

Three layers:
  A. Spend pacing:  cumulative actual vs cumulative planned (seasonal curve)
  B. Signup pacing: cumulative actual signups vs target signups (by channel)
  C. ARR waterfall: reverse-engineer channel signup targets from top-line ARR

The closed-loop moment lives here: if a channel is behind on signups, compute
the corrective spend shift needed to close the gap in remaining weeks AT THAT
CHANNEL'S CURRENT CAC. That recommendation is staged as a parallel
"Pacing-Corrected Allocation" line on the Monday Allocation Review so the lead
sees Math-Optimal vs Pacing-Corrected side-by-side.

Why this is not just a dashboard: pacing is an INPUT to next week's allocator,
not just a report. That's the loop closing.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import config


# ── Quarter math ─────────────────────────────────────────────────────

def quarter_weeks() -> list[str]:
    start = date.fromisoformat(config.QUARTER_START)
    return [(start + timedelta(weeks=i)).isoformat() for i in range(config.QUARTER_WEEKS)]


def week_index_in_quarter(week_start: str) -> int | None:
    """Return 0-indexed week position within the quarter, or None if outside."""
    weeks = quarter_weeks()
    if week_start not in weeks:
        return None
    return weeks.index(week_start)


def cumulative_planned_share(through_week_idx: int) -> float:
    """Share of quarterly total planned through (and including) this week."""
    if through_week_idx < 0:
        return 0.0
    end = min(through_week_idx + 1, config.QUARTER_WEEKS)
    return sum(config.PACING_CURVE[:end])


def planned_weekly_envelope(segment: str, week_start: str) -> float:
    """
    Seasonally-adjusted spend envelope for a single week, derived from the
    quarterly plan curve. The allocator uses this (not a flat 1/13) so its
    investment target tracks the same seasonal plan as pacing — ramping into
    the offline event, tapering to quarter close.

    Falls back to the flat weekly envelope outside the quarter window.
    """
    weekly = config.FINANCE_GUARDRAILS[segment]["weekly_envelope"]
    wi = week_index_in_quarter(week_start)
    if wi is None:
        return float(weekly)
    quarterly = weekly * config.QUARTER_WEEKS
    return quarterly * config.PACING_CURVE[wi]


# ── A. Spend pacing ──────────────────────────────────────────────────

def spend_pacing(perf_rows: list[dict], segment: str, current_week: str) -> dict[str, Any]:
    """Cumulative actual vs cumulative planned spend through the current week."""
    weeks = quarter_weeks()
    wi = week_index_in_quarter(current_week)
    envelope = config.FINANCE_GUARDRAILS[segment]["weekly_envelope"]
    quarterly_envelope = envelope * config.QUARTER_WEEKS

    # Per-week actual spend (only for weeks in this quarter that have data)
    actual_by_week: dict[str, float] = defaultdict(float)
    for r in perf_rows:
        if r["segment"] == segment and r["week_start"] in weeks:
            actual_by_week[r["week_start"]] += float(r["spend"])

    series = []
    cum_actual = 0.0
    for i, w in enumerate(weeks):
        planned_week = quarterly_envelope * config.PACING_CURVE[i]
        cum_planned = quarterly_envelope * cumulative_planned_share(i)
        is_actual = wi is not None and i <= wi
        if is_actual:
            cum_actual += actual_by_week.get(w, 0.0)
        series.append({
            "week_idx": i + 1,
            "week_start": w,
            "planned_week": round(planned_week),
            "cum_planned": round(cum_planned),
            "actual_week": round(actual_by_week.get(w, 0.0)) if is_actual else None,
            "cum_actual": round(cum_actual) if is_actual else None,
            "is_event_week": (i + 1) == config.PACING_EVENT_WEEK,
            "phase": "actual" if is_actual else "forecast",
        })

    cur_idx = wi if wi is not None else 0
    cum_planned_now = quarterly_envelope * cumulative_planned_share(cur_idx)
    cum_actual_now = cum_actual
    pacing_pct = (cum_actual_now / cum_planned_now) if cum_planned_now else 0
    delta_dollars = cum_actual_now - cum_planned_now

    return {
        "quarter_label": config.QUARTER_LABEL,
        "event_week": config.PACING_EVENT_WEEK,
        "event_name": config.PACING_EVENT_NAME,
        "current_week_idx": cur_idx + 1,
        "weeks_in_quarter": config.QUARTER_WEEKS,
        "weeks_remaining": max(0, config.QUARTER_WEEKS - cur_idx - 1),
        "quarterly_envelope": quarterly_envelope,
        "cum_actual": round(cum_actual_now),
        "cum_planned": round(cum_planned_now),
        "delta_dollars": round(delta_dollars),
        "pacing_pct": round(pacing_pct * 100, 1),
        "status": _status(pacing_pct),
        "series": series,
    }


def channel_spend_series(perf_rows: list[dict], segment: str) -> dict[str, list[dict]]:
    """Per-channel weekly actual spend, used for filtered spend-pacing chart."""
    weeks = quarter_weeks()
    by_ch: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in perf_rows:
        if r["segment"] == segment and r["week_start"] in weeks:
            by_ch[r["channel"]][r["week_start"]] += float(r["spend"])

    out = {}
    for ch in config.CHANNELS.get(segment, []):
        out[ch] = [
            {"week_idx": i + 1, "week_start": w, "spend": round(by_ch[ch].get(w, 0.0))}
            for i, w in enumerate(weeks)
        ]
    return out


# ── B. Signup / sub / pipeline pacing ────────────────────────────────

def signup_pacing(
    perf_rows: list[dict],
    funnel_rows: list[dict],
    segment: str,
    current_week: str,
    free_to_paid_override: float | None = None,
    activation_override: float | None = None,
    arr_target_override: float | None = None,
) -> dict[str, Any]:
    """
    Reverse-engineer signup targets from top-line target, then compare to actuals.

    Consumer:  ARR target -> paying subs -> activated -> signups -> per-channel
    Enterprise: pipeline target -> qualified signups -> per-channel
    """
    weeks = quarter_weeks()
    wi = week_index_in_quarter(current_week)
    cur_idx = wi if wi is not None else 0
    target_cfg = config.QUARTERLY_TARGETS[segment]

    # ── Compute quarterly signup target ──
    if target_cfg["type"] == "arr_and_subs":
        arpu = target_cfg["consumer_arpu_annual"]
        arr_target = arr_target_override or target_cfg["arr_target_usd"]
        subs_target = arr_target / arpu
        f2p = free_to_paid_override or target_cfg["free_to_paid_assumption"]
        activation = activation_override or target_cfg["activation_rate_assumption"]
        activated_target = subs_target / max(f2p, 0.001)
        signup_target = activated_target / max(activation, 0.001)
        waterfall = [
            {"label": "Net-new ARR target",          "value": f"${arr_target:,.0f}", "source": "Finance / GTM leadership"},
            {"label": "/ Annual ARPU",               "value": f"${arpu}", "source": "Core plan, $20/mo"},
            {"label": "= Paying subs needed",        "value": f"{subs_target:,.0f}", "source": "Derived"},
            {"label": "/ Free->Paid rate",           "value": f"{f2p*100:.1f}%", "source": "Funnel module (4w trailing cohort)"},
            {"label": "= Activated users needed",    "value": f"{activated_target:,.0f}", "source": "Derived"},
            {"label": "/ Activation rate",           "value": f"{activation*100:.1f}%", "source": "Funnel module"},
            {"label": "= Total signups needed (Q)",  "value": f"{signup_target:,.0f}", "source": "Derived"},
        ]
        unit_label = "signups"
        if arr_target >= 1_000_000:
            topline_label = f"${arr_target/1_000_000:.1f}M ARR"
        else:
            topline_label = f"${arr_target/1_000:.0f}K ARR"
    else:
        per_signup = target_cfg["pipeline_value_per_signup"]
        pipe_target = arr_target_override or target_cfg["pipeline_target_usd"]
        signup_target = pipe_target / per_signup
        waterfall = [
            {"label": "Net-new pipeline target",     "value": f"${pipe_target:,.0f}", "source": "Sales leadership"},
            {"label": "/ Pipeline $ per signup",     "value": f"${per_signup:,.0f}", "source": "Avg deal x win-rate proxy"},
            {"label": "= Qualified signups needed",  "value": f"{signup_target:,.0f}", "source": "Derived"},
        ]
        unit_label = "qualified signups"
        if pipe_target >= 1_000_000:
            topline_label = f"${pipe_target/1_000_000:.1f}M Pipeline"
        else:
            topline_label = f"${pipe_target/1_000:.0f}K Pipeline"

    # ── Per-channel signup attribution share (from quarter-to-date funnel data) ──
    ch_signups: dict[str, float] = defaultdict(float)
    for r in funnel_rows:
        if r["segment"] == segment and r["week_start"] in weeks:
            ch_signups[r["channel"]] += r["signups"]
    total_signups_qtd = sum(ch_signups.values()) or 1.0
    attribution_share = {ch: v / total_signups_qtd for ch, v in ch_signups.items()}

    # If no funnel data yet, fall back to even distribution across channels
    if total_signups_qtd <= 1.0:
        chans = config.CHANNELS.get(segment, [])
        attribution_share = {ch: 1.0 / max(len(chans), 1) for ch in chans}

    # ── Per-channel target signups (Q-total) using attribution share ──
    channel_targets_q = {ch: signup_target * share for ch, share in attribution_share.items()}

    # ── Per-week actual signups by channel, cumulative ──
    actual_by_ch_week: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in funnel_rows:
        if r["segment"] == segment and r["week_start"] in weeks:
            actual_by_ch_week[r["channel"]][r["week_start"]] += r["signups"]

    channel_rows = []
    total_actual = 0.0
    total_target_cum = 0.0
    for ch in config.CHANNELS.get(segment, []):
        ch_q_target = channel_targets_q.get(ch, 0.0)
        # Distribute Q target across weeks using the same pacing curve
        cum_target_now = ch_q_target * cumulative_planned_share(cur_idx)
        cum_actual = sum(
            actual_by_ch_week[ch].get(w, 0.0) for i, w in enumerate(weeks) if i <= cur_idx
        )
        pacing_pct = cum_actual / cum_target_now if cum_target_now else 0
        gap_units = cum_actual - cum_target_now
        # Per-channel CAC for corrective shift math (use latest week)
        latest = weeks[cur_idx] if cur_idx < len(weeks) else weeks[-1]
        ch_spend_latest = sum(float(r["spend"]) for r in perf_rows
                              if r["segment"] == segment and r["channel"] == ch and r["week_start"] == latest)
        ch_signups_latest = actual_by_ch_week[ch].get(latest, 0.0)
        ch_cac = ch_spend_latest / ch_signups_latest if ch_signups_latest else 0
        # Weeks remaining to close gap
        weeks_remaining = max(1, config.QUARTER_WEEKS - cur_idx - 1)
        gap_to_close_q = ch_q_target - cum_actual  # signups still needed
        # If gap negative (ahead), no corrective shift needed
        corrective_spend = max(0, gap_to_close_q - (ch_q_target - cum_target_now)) * ch_cac if ch_cac else 0
        # The corrective amount is the gap_units shortfall split over remaining weeks
        weekly_corrective = (-gap_units / weeks_remaining * ch_cac) if (gap_units < 0 and ch_cac and weeks_remaining) else 0
        channel_rows.append({
            "channel": ch,
            "label": config.CHANNEL_LABELS.get(ch, ch),
            "quarter_target": round(ch_q_target),
            "cum_target_now": round(cum_target_now),
            "cum_actual": round(cum_actual),
            "gap_units": round(gap_units),
            "pacing_pct": round(pacing_pct * 100, 1),
            "status": _status(pacing_pct),
            "attribution_share_pct": round(attribution_share.get(ch, 0) * 100, 1),
            "cac": round(ch_cac, 2),
            "weeks_remaining": weeks_remaining,
            "weekly_corrective_spend": round(weekly_corrective),
        })
        total_actual += cum_actual
        total_target_cum += cum_target_now

    overall_pacing_pct = (total_actual / total_target_cum) if total_target_cum else 0
    # Corrective spend only flows into channels that are BOTH behind AND under the
    # CAC ceiling — pacing pressure must not push budget into inefficient channels.
    cac_ceiling = config.FINANCE_GUARDRAILS[segment]["cac_ceiling"]
    behind_channels = [
        c for c in channel_rows
        if c["gap_units"] < 0 and c["weekly_corrective_spend"] > 0
        and 0 < c["cac"] <= cac_ceiling
    ]
    behind_channels.sort(key=lambda c: c["gap_units"])  # most behind first

    # Per-channel weekly series for charting (actual + planned)
    series_by_channel: dict[str, list[dict]] = {}
    for ch in config.CHANNELS.get(segment, []):
        ch_q_target = channel_targets_q.get(ch, 0.0)
        series = []
        cum_a = 0.0
        for i, w in enumerate(weeks):
            cum_p = ch_q_target * cumulative_planned_share(i)
            is_actual = i <= cur_idx
            if is_actual:
                cum_a += actual_by_ch_week[ch].get(w, 0.0)
            series.append({
                "week_idx": i + 1,
                "week_start": w,
                "cum_planned": round(cum_p),
                "cum_actual": round(cum_a) if is_actual else None,
                "is_event_week": (i + 1) == config.PACING_EVENT_WEEK,
                "phase": "actual" if is_actual else "forecast",
            })
        series_by_channel[ch] = series

    return {
        "segment": segment,
        "quarter_label": config.QUARTER_LABEL,
        "current_week_idx": cur_idx + 1,
        "weeks_remaining": max(0, config.QUARTER_WEEKS - cur_idx - 1),
        "topline_label": topline_label,
        "unit_label": unit_label,
        "quarterly_signup_target": round(signup_target),
        "cum_target_now": round(total_target_cum),
        "cum_actual": round(total_actual),
        "gap_units": round(total_actual - total_target_cum),
        "overall_pacing_pct": round(overall_pacing_pct * 100, 1),
        "overall_status": _status(overall_pacing_pct),
        "waterfall": waterfall,
        "channels": channel_rows,
        "behind_channels": behind_channels,
        "series_by_channel": series_by_channel,
        "assumptions_used": {
            "free_to_paid": free_to_paid_override or target_cfg.get("free_to_paid_assumption"),
            "activation": activation_override or target_cfg.get("activation_rate_assumption"),
            "arpu": target_cfg.get("consumer_arpu_annual") or target_cfg.get("pipeline_value_per_signup"),
        },
    }


# ── C. Closed-loop: corrective allocation shift ──────────────────────

def build_corrective_recommendation(
    signup_pacing_data: dict,
    spend_pacing_data: dict,
    segment: str,
    incrementality_signals: dict[str, dict] | None = None,
) -> dict[str, Any] | None:
    """
    Construct a Pacing-Corrected Allocation that addresses the biggest gaps.
    Shifts weekly budget INTO behind channels at their current CAC.
    Caps at the segment's max_weekly_shift_pct guardrail to stay honest.

    Corrective budget never flows into channels a geo-holdout has shown to be
    non-incremental — chasing a pacing target into proven-non-causal spend would
    just buy lower-quality volume.
    """
    non_incremental = set((incrementality_signals or {}).keys())
    behind = [
        c for c in signup_pacing_data.get("behind_channels", [])
        if c["channel"] not in non_incremental
    ]
    if not behind:
        return None

    envelope = config.FINANCE_GUARDRAILS[segment]["weekly_envelope"]
    max_shift = envelope * config.FINANCE_GUARDRAILS[segment]["max_weekly_shift_pct"]

    total_corrective_needed = sum(c["weekly_corrective_spend"] for c in behind)
    capped = min(total_corrective_needed, max_shift)
    cap_hit = total_corrective_needed > max_shift
    gap_closed_pct = round((capped / total_corrective_needed) * 100) if total_corrective_needed else 100
    weeks_remaining = signup_pacing_data["weeks_remaining"]

    # Distribute capped corrective across behind channels proportional to gap
    total_gap = sum(-c["gap_units"] for c in behind) or 1
    shifts = []
    for c in behind:
        weight = (-c["gap_units"]) / total_gap
        shift_amount = round(capped * weight)
        shifts.append({
            "channel": c["channel"],
            "label": c["label"],
            "into_channel": shift_amount,
            "rationale": (
                f"Behind by {-c['gap_units']:,} signups ({c['pacing_pct']}% pacing). "
                f"At CAC ${c['cac']}, +${shift_amount:,}/wk over {weeks_remaining}w "
                f"recovers shortfall at current efficiency."
            ),
        })

    headline = (
        f"Reallocate +${capped:,.0f}/wk into {', '.join(s['label'] for s in shifts)} "
        f"to recover the quarter-to-date shortfall over the remaining {weeks_remaining} weeks "
        f"— closes ~{gap_closed_pct}% of the gap within finance guardrails."
    )

    constraint_note = (
        f"Bounded by the {config.FINANCE_GUARDRAILS[segment]['max_weekly_shift_pct']*100:.0f}% "
        f"weekly-shift guardrail and the ${config.FINANCE_GUARDRAILS[segment]['cac_ceiling']} "
        f"CAC ceiling (corrective budget flows only to channels under the ceiling)."
    )
    if cap_hit:
        constraint_note += (
            f" Full closure would require +${total_corrective_needed:,.0f}/wk; the remaining "
            f"~{100 - gap_closed_pct}% calls for conversion-rate (funnel) improvement, not budget alone."
        )

    return {
        "id": "pacing_corrected_alloc",
        "headline": headline,
        "total_shift_per_week": round(capped),
        "uncapped_total": round(total_corrective_needed),
        "gap_closed_pct": gap_closed_pct,
        "cap_hit": cap_hit,
        "weeks_remaining": weeks_remaining,
        "shifts": shifts,
        "constraint_note": constraint_note,
        "decision_id": "pacing_corrected_alloc",
    }


# ── Helpers ─────────────────────────────────────────────────────────

def _status(pct: float) -> str:
    if pct >= 0.98:
        return "on_track"
    if pct >= 0.90:
        return "at_risk"
    return "behind"


def build_pacing_state(
    perf_rows: list[dict],
    funnel_rows: list[dict],
    segment: str,
    current_week: str,
    free_to_paid_override: float | None = None,
    activation_override: float | None = None,
    arr_target_override: float | None = None,
    incrementality_signals: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Aggregate everything pacing-related for the ingest layer."""
    spend = spend_pacing(perf_rows, segment, current_week)
    signups = signup_pacing(
        perf_rows, funnel_rows, segment, current_week,
        free_to_paid_override=free_to_paid_override,
        activation_override=activation_override,
        arr_target_override=arr_target_override,
    )
    corrective = build_corrective_recommendation(signups, spend, segment, incrementality_signals)
    channel_spend = channel_spend_series(perf_rows, segment)

    return {
        "quarter_label": config.QUARTER_LABEL,
        "quarter_start": config.QUARTER_START,
        "weeks_in_quarter": config.QUARTER_WEEKS,
        "event_week": config.PACING_EVENT_WEEK,
        "event_name": config.PACING_EVENT_NAME,
        "current_week_idx": spend["current_week_idx"],
        "weeks_remaining": spend["weeks_remaining"],
        "spend": spend,
        "signups": signups,
        "channel_spend_series": channel_spend,
        "corrective_recommendation": corrective,
        "production_scale_note": (
            f"Sample-scale defaults. Production target would be ~"
            f"${config.QUARTERLY_TARGETS[segment].get('arr_target_production') or config.QUARTERLY_TARGETS[segment].get('pipeline_target_production', 0):,.0f}. "
            f"ARR / Free->Paid / Activation are editable in the tab to stress-test sensitivity."
        ),
    }
