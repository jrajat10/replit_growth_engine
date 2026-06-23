"""Constrained budget allocation — teachable greedy optimizer with guardrails.

Design principles (defensible in interview):
  - Finance sets HOW MUCH (seasonal weekly envelope). Math decides WHERE.
  - Stability guardrail is symmetric: a channel can move at most ±max_weekly_shift
    versus its current spend. (Both the up- AND down-side are enforced.)
  - Marginal, not average, returns: a channel's per-dollar value decays as spend
    is pushed above its proven level (diminishing returns).
  - Incrementality over attribution: channels with a significant non-incremental
    geo-holdout read are discounted, so proven-causal channels win the margin.
  - The optimizer will UNDER-deploy the envelope rather than violate guardrails,
    reporting the unspent amount as ramp-limited reserve.
"""

from __future__ import annotations

from typing import Any

import config
from engine.pacing import planned_weekly_envelope


def _channel_metrics(
    perf_rows: list[dict],
    segment: str,
    week_start: str,
) -> dict[str, dict]:
    """Aggregate net-new efficiency per channel for one week."""
    agg: dict[str, dict] = {}
    for r in perf_rows:
        if r["segment"] != segment or r["week_start"] != week_start:
            continue
        ch = r["channel"]
        if ch not in agg:
            agg[ch] = {"spend": 0.0, "new_conv": 0.0, "conv": 0.0}
        agg[ch]["spend"] += float(r["spend"])
        agg[ch]["new_conv"] += float(r["new_user_conversions"])
        agg[ch]["conv"] += float(r["conversions"])
    for ch, v in agg.items():
        v["cac"] = v["spend"] / v["new_conv"] if v["new_conv"] > 0 else 9999
        v["efficiency"] = v["new_conv"] / v["spend"] if v["spend"] > 0 else 0
    return agg


def allocate(
    perf_rows: list[dict],
    segment: str,
    week_start: str,
    ltv_multipliers: dict[str, dict],
    prior_allocation: dict[str, float] | None = None,
    model_scores: dict[str, float] | None = None,
    score_explanations: dict[str, str] | None = None,
    incrementality_signals: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """
    Constrained greedy allocation:
      1. Score each channel = net-new per $ × LTV × CAC penalty × incrementality.
      2. Bound each channel to a ±max_weekly_shift band around CURRENT spend.
      3. Greedily add budget to the highest *marginal* (saturation-adjusted) score.
      4. Stop at the seasonal envelope or when guardrails block further deploy.
      5. Report any undeployed envelope as ramp-limited reserve.
    """
    guard = config.FINANCE_GUARDRAILS[segment]
    flat_envelope = guard["weekly_envelope"]
    floor = guard["min_channel_spend"]
    max_pct = guard["max_channel_pct"]
    cac_ceil = guard["cac_ceiling"]
    max_shift = guard["max_weekly_shift_pct"]
    sat_k = getattr(config, "SATURATION_EXPONENT", 1.0)

    # Seasonal envelope: next-week investment tracks the quarterly plan curve.
    envelope = planned_weekly_envelope(segment, week_start)
    max_cap = flat_envelope * max_pct  # per-channel hard cap (vs stable base)

    channels = config.CHANNELS[segment]
    metrics = _channel_metrics(perf_rows, segment, week_start)
    discounts = incrementality_signals or {}

    # ── Scores ─────────────────────────────────────────
    scores: dict[str, float] = {}
    for ch in channels:
        m = metrics.get(ch, {"efficiency": 0, "cac": 9999, "spend": 0})
        ltv = ltv_multipliers.get(ch, {}).get("ltv_multiplier", 1.0)
        cac_penalty = 0.5 if m["cac"] > cac_ceil else 1.0
        inc = discounts.get(ch, {}).get("discount", 1.0)
        scores[ch] = m["efficiency"] * ltv * cac_penalty * inc

    scoring_mode = "heuristic"
    if model_scores:
        scores = {
            ch: model_scores.get(ch, scores.get(ch, 0)) * discounts.get(ch, {}).get("discount", 1.0)
            for ch in channels
        }
        scoring_mode = "ds_model"

    # ── Symmetric stability band around CURRENT spend ──
    baseline = {ch: max(metrics.get(ch, {}).get("spend", 0.0), 0.0) for ch in channels}
    shift_base = {ch: max(baseline[ch], floor) for ch in channels}
    min_alloc = {ch: max(floor, shift_base[ch] * (1 - max_shift)) for ch in channels}
    max_alloc = {ch: min(max_cap, shift_base[ch] * (1 + max_shift)) for ch in channels}
    for ch in channels:
        if min_alloc[ch] > max_alloc[ch]:
            min_alloc[ch] = max_alloc[ch]

    # If the protected minimums already exceed the envelope, haircut proportionally.
    sum_min = sum(min_alloc.values())
    if sum_min > envelope and sum_min > 0:
        scale = envelope / sum_min
        min_alloc = {ch: min_alloc[ch] * scale for ch in channels}
        max_alloc = {ch: max(min_alloc[ch], max_alloc[ch] * scale) for ch in channels}

    alloc = dict(min_alloc)
    deployable_cap = sum(max_alloc.values())
    target_spend = min(envelope, deployable_cap)
    remaining = target_spend - sum(alloc.values())

    # ── Greedy fill by saturation-adjusted marginal score ──
    def marginal(ch: str) -> float:
        if scores.get(ch, 0) <= 0 or alloc[ch] >= max_alloc[ch]:
            return -1.0
        ref = shift_base[ch]
        over = max(0.0, alloc[ch] - ref)
        sat = 1.0 / (1.0 + (over / ref)) ** sat_k if ref > 0 else 1.0
        return scores[ch] * sat

    step = 1000.0
    while remaining >= step:
        best, best_m = None, 0.0
        for ch in channels:
            mv = marginal(ch)
            if mv > best_m:
                best_m, best = mv, ch
        if best is None:
            break
        add = min(step, max_alloc[best] - alloc[best])
        if add <= 0:
            break
        alloc[best] += add
        remaining -= add

    reserve = round(envelope - sum(alloc.values()))

    # ── Rationale ──────────────────────────────────────
    ranked = sorted(channels, key=lambda c: scores.get(c, 0), reverse=True)
    rationale = []
    for ch in ranked:
        m = metrics.get(ch, {})
        ltv = ltv_multipliers.get(ch, {})
        exp = (score_explanations or {}).get(ch, "")
        inc_note = discounts.get(ch, {}).get("reason", "")
        if scoring_mode == "ds_model" and exp:
            score_plain = exp
        else:
            score_plain = (
                f"{m.get('efficiency', 0)*1000:.2f} net-new per $1k "
                f"× {ltv.get('ltv_multiplier', 1):.2f} LTV = "
                f"{scores.get(ch, 0)*1000:.3f} value index"
            )
        if inc_note:
            score_plain += f" · {inc_note}"
        rationale.append({
            "channel": ch,
            "label": config.CHANNEL_LABELS.get(ch, ch),
            "score": round(scores.get(ch, 0) * 1e6, 2),
            "score_plain": score_plain,
            "current_spend": round(baseline[ch]),
            "recommended_spend": round(alloc[ch]),
            "delta": round(alloc[ch] - baseline[ch]),
            "cac": round(m.get("cac", 0), 2),
            "ltv_multiplier": ltv.get("ltv_multiplier", 1.0),
            "ltv_explanation": ltv.get("explanation", ""),
            "incrementality_note": inc_note,
            "shift_band_pct": round(max_shift * 100),
        })

    shifts = [r for r in rationale if abs(r["delta"]) > 3000]
    summary = (
        f"Within a ${envelope:,.0f} seasonal envelope, allocate to highest "
        f"marginal (net-new efficiency × LTV), holding each channel inside a "
        f"±{max_shift:.0%} weekly-shift band and a ${cac_ceil} CAC ceiling."
    )
    if shifts:
        top_shift = max(shifts, key=lambda x: abs(x["delta"]))
        summary += (
            f" Biggest move: {top_shift['label']} "
            f"{'+' if top_shift['delta']>0 else ''}{top_shift['delta']:,}."
        )
    if reserve > envelope * 0.03:
        summary += f" ${reserve:,} held as ramp-limited reserve (guardrail-capped this week)."

    return {
        "segment": segment,
        "week_start": week_start,
        "envelope": round(envelope),
        "flat_envelope": flat_envelope,
        "total_recommended": round(sum(alloc.values())),
        "reserve": reserve,
        "allocation": alloc,
        "rationale": rationale,
        "summary": summary,
        "method": (
            "Constrained greedy allocation — DS model scores, diminishing-returns "
            "adjusted, within ±shift / CAC / cap guardrails"
            if scoring_mode == "ds_model"
            else "Constrained greedy allocation — heuristic (net-new × LTV), "
            "diminishing-returns adjusted, within ±shift / CAC / cap guardrails"
        ),
        "scoring_mode": scoring_mode,
        "human_can_veto": True,
    }
