"""Constrained budget allocation — simple, teachable LP-style optimizer."""

from __future__ import annotations

from typing import Any

import config


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
) -> dict[str, Any]:
    """
    Simple constrained allocation:
    1. Score each channel = net-new conversions per $ × LTV multiplier
    2. Start at minimum spend (floor)
    3. Greedily add budget to highest score until envelope exhausted
    4. Respect per-channel cap and CAC ceiling
    5. Limit shift from prior week (stability)

    Finance decides HOW MUCH (envelope). Math decides WHERE.
    """
    guard = config.FINANCE_GUARDRAILS[segment]
    envelope = guard["weekly_envelope"]
    floor = guard["min_channel_spend"]
    max_pct = guard["max_channel_pct"]
    max_cap = envelope * max_pct
    cac_ceil = guard["cac_ceiling"]
    max_shift = guard["max_weekly_shift_pct"]

    channels = config.CHANNELS[segment]
    metrics = _channel_metrics(perf_rows, segment, week_start)

    scores = {}
    for ch in channels:
        m = metrics.get(ch, {"efficiency": 0, "cac": 9999, "spend": 0})
        ltv = ltv_multipliers.get(ch, {}).get("ltv_multiplier", 1.0)
        eff = m["efficiency"]
        # Penalize channels above CAC ceiling
        cac_penalty = 0.5 if m["cac"] > cac_ceil else 1.0
        scores[ch] = eff * ltv * cac_penalty

    scoring_mode = "heuristic"
    if model_scores:
        scores = {ch: model_scores.get(ch, scores.get(ch, 0)) for ch in channels}
        scoring_mode = "ds_model"

    # Initialize at floor
    alloc = {ch: floor for ch in channels}
    remaining = envelope - sum(alloc.values())

    # Prior for stability
    if prior_allocation:
        for ch in channels:
            prior = prior_allocation.get(ch, floor)
            max_up = prior * (1 + max_shift)
            max_down = prior * (1 - max_shift)
            alloc[ch] = max(floor, min(alloc[ch], max_up))

    # Greedy fill by score
    ranked = sorted(channels, key=lambda c: scores.get(c, 0), reverse=True)
    step = 2000
    while remaining >= step:
        placed = False
        for ch in ranked:
            if alloc[ch] + step <= max_cap and scores.get(ch, 0) > 0:
                if prior_allocation:
                    prior = prior_allocation.get(ch, floor)
                    if alloc[ch] + step > prior * (1 + max_shift):
                        continue
                alloc[ch] += step
                remaining -= step
                placed = True
                break
        if not placed:
            break

    # Normalize if rounding left slack — give to top channel
    slack = envelope - sum(alloc.values())
    if slack > 0 and ranked:
        top = ranked[0]
        alloc[top] = min(alloc[top] + slack, max_cap)

    rationale = []
    for ch in ranked:
        m = metrics.get(ch, {})
        ltv = ltv_multipliers.get(ch, {})
        exp = (score_explanations or {}).get(ch, "")
        if scoring_mode == "ds_model" and exp:
            score_plain = exp
        else:
            score_plain = (
                f"{m.get('efficiency', 0)*1000:.2f} net-new per $1k spend "
                f"× {ltv.get('ltv_multiplier', 1):.2f} LTV = "
                f"{scores.get(ch, 0)*1000:.3f} value index"
            )
        rationale.append({
            "channel": ch,
            "label": config.CHANNEL_LABELS.get(ch, ch),
            "score": round(scores.get(ch, 0) * 1e6, 2),
            "score_plain": score_plain,
            "current_spend": round(m.get("spend", 0)),
            "recommended_spend": round(alloc[ch]),
            "delta": round(alloc[ch] - m.get("spend", 0)),
            "cac": round(m.get("cac", 0), 2),
            "ltv_multiplier": ltv.get("ltv_multiplier", 1.0),
            "ltv_explanation": ltv.get("explanation", ""),
        })

    shifts = [r for r in rationale if abs(r["delta"]) > 3000]
    summary = (
        f"Within ${envelope:,.0f} envelope, allocate to highest "
        f"(net-new efficiency × LTV multiplier), respecting "
        f"${floor:,} floor, {max_pct:.0%} cap, ${cac_ceil} CAC ceiling."
    )
    if shifts:
        top_shift = max(shifts, key=lambda x: abs(x["delta"]))
        summary += (
            f" Biggest move: {top_shift['label']} "
            f"{'+' if top_shift['delta']>0 else ''}{top_shift['delta']:,}."
        )

    return {
        "segment": segment,
        "week_start": week_start,
        "envelope": envelope,
        "total_recommended": sum(alloc.values()),
        "allocation": alloc,
        "rationale": rationale,
        "summary": summary,
        "method": (
            "Constrained greedy allocation (DS model scores, within guardrails)"
            if scoring_mode == "ds_model"
            else "Constrained greedy allocation (heuristic efficiency × LTV, within guardrails)"
        ),
        "scoring_mode": scoring_mode,
        "human_can_veto": True,
    }
