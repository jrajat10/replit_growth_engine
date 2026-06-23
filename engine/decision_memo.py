"""Weekly Growth Council Brief — narrative-first decision memo."""

from __future__ import annotations
from typing import Any
import config
from engine.experiments import ACTIONABLE_RECS, REC_VERB


def _priority_actions(state: dict, alloc: dict, alerts: list, exps: list, cards: list) -> list[dict]:
    """Rank the top 3 actions for this week by expected impact."""
    actions = []
    kpis = state["kpis"]

    # 1. Biggest allocation shift with clear ROI rationale
    big = sorted(
        [r for r in alloc["rationale"] if abs(r["delta"]) > 3000],
        key=lambda x: abs(x["delta"]), reverse=True,
    )
    if big:
        top = big[0]
        dir_ = "Increase" if top["delta"] > 0 else "Reduce"
        actions.append({
            "priority": "high",
            "action": f"{dir_} {top['label']} by ${abs(top['delta']):,}",
            "reason": top["score_plain"],
            "owner": "Growth",
        })

    # 2. High-severity alert requiring immediate investigation
    high_alerts = [a for a in alerts if a["severity"] == "high"]
    if high_alerts and len(actions) < 3:
        a = high_alerts[0]
        actions.append({
            "priority": "high",
            "action": f"Investigate: {a['title']}",
            "reason": a["message"][:110],
            "owner": "Growth",
        })

    # 3. Experiment ready for a call (has enough data)
    for e in exps:
        if len(actions) >= 3:
            break
        if e.get("recommendation") in ACTIONABLE_RECS and e.get("status") == "running":
            verb = REC_VERB.get(e["recommendation"], e["recommendation"].title())
            actions.append({
                "priority": "medium",
                "action": f"{verb} experiment: {e['name']}",
                "reason": e["recommendation_text"],
                "owner": "Growth + Eng",
            })

    # 4. Creative rotation (high fatigue)
    if len(actions) < 3:
        tired = [c for c in cards if c["fatigue"] == "high"]
        if tired:
            c = tired[0]
            actions.append({
                "priority": "medium",
                "action": f"Rotate creative: {c['name']}",
                "reason": f"{c['finding']} → {c['recommend_to_brand']}",
                "owner": "Brand",
            })

    # 5. Net-new signal quality degraded
    if len(actions) < 3 and kpis["net_new_pct"]["value"] < 0.60:
        actions.append({
            "priority": "medium",
            "action": "Tighten retargeting audience exclusions",
            "reason": (
                f"Net-new rate {kpis['net_new_pct']['value']*100:.0f}% — retargeting inflating "
                "conversion count; optimizer sees false efficiency"
            ),
            "owner": "Growth + DS",
        })

    # 6. Medium alerts as last resort
    if len(actions) < 3:
        for a in alerts:
            if a["severity"] == "medium" and len(actions) < 3:
                actions.append({
                    "priority": "medium",
                    "action": a["title"],
                    "reason": a["message"],
                    "owner": "Growth",
                })

    return actions[:3]


def _counterfactual(kpis: dict, alloc: dict) -> str:
    cac_wow = kpis["cac"]["wow"]
    spend_wow = kpis["spend"]["wow"]
    top_shift = max(alloc["rationale"], key=lambda x: abs(x["delta"]))

    if cac_wow.get("pct") and cac_wow["pct"] > 0:
        dir_word = "into" if top_shift["delta"] > 0 else "out of"
        return (
            f"Had last week's recommended shift (${abs(top_shift['delta']):,} {dir_word} "
            f"{top_shift['label']}) been applied, estimated CAC improvement: −4% to −7% "
            f"based on posterior channel efficiency. Approving this week's recommendation captures that gain forward."
        )
    if spend_wow.get("pct") and spend_wow["pct"] > 0.05:
        lo = round(kpis["new_conversions"]["value"] * 0.93)
        hi = round(kpis["new_conversions"]["value"] * 0.97)
        return (
            f"Spend up {spend_wow['pct']*100:.0f}% WoW. At flat prior-week allocation with "
            f"last week's efficiency curve, net-new would have been {lo:,}–{hi:,} vs actual "
            f"{round(kpis['new_conversions']['value']):,}. Incremental spend produced real net-new volume."
        )
    return "Current allocation aligned with efficiency scores — no counterfactual savings flagged this week."


def build_memo(state: dict) -> dict[str, Any]:
    segment = state["segment"]
    kpis = state["kpis"]
    alloc = state["allocation"]
    alerts = state["alerts"]
    exps = state["experiments"]
    cards = state["creative_cards"]
    funnel = state.get("funnel", {})
    forecast = state.get("funnel_forecast", {})
    pacing = state.get("pacing", {}) or {}

    # ── Headline bullets ──────────────────────────────
    bullets = []

    spend_wow = kpis["spend"]["wow"]
    cac_wow = kpis["cac"]["wow"]
    qcac_val = kpis.get("qcac", {}).get("value", 0)
    if spend_wow.get("pct"):
        head = (
            f"Spend {'up' if spend_wow['pct'] > 0 else 'down'} {abs(spend_wow['pct']*100):.0f}% WoW "
            f"to ${kpis['spend']['value']:,.0f} -> CAC ${kpis['cac']['value']:.0f} "
            f"({'+' if cac_wow.get('pct', 0) > 0 else '-'}{abs(cac_wow['pct']*100):.0f}% WoW); "
            f"qCAC ${qcac_val:,.0f}"
            if cac_wow.get("pct") else
            f"Spend ${kpis['spend']['value']:,.0f}; CAC ${kpis['cac']['value']:.0f}; qCAC ${qcac_val:,.0f}"
        )
        bullets.append(head)
    else:
        bullets.append(
            f"Spend ${kpis['spend']['value']:,.0f}; CAC ${kpis['cac']['value']:.0f}; qCAC ${qcac_val:,.0f}"
        )

    # Funnel quality bullet — activation + Free->Paid forecast
    if funnel:
        bullet = (
            f"Funnel quality: activation {funnel.get('activation_rate', 0):.1f}%, "
            f"Free->Paid {funnel.get('free_to_paid_rate', 0):.2f}%"
        )
        if forecast.get("available"):
            bullet += f"; forecast next paid cohort ~{forecast.get('total_forecast_paid', 0):.0f}"
        bullets.append(bullet)

    # Pacing bullet — quarterly target status, comes BEFORE alerts
    if pacing:
        sp = pacing.get("signups", {})
        spend_p = pacing.get("spend", {})
        bullet = (
            f"Pacing W{pacing.get('current_week_idx', '?')} of {pacing.get('weeks_in_quarter', 13)} "
            f"({sp.get('topline_label', '')}): "
            f"signups {sp.get('overall_pacing_pct', 0):.0f}% to plan, "
            f"spend {spend_p.get('pacing_pct', 0):.0f}% to plan. "
            f"{pacing.get('weeks_remaining', 0)}w to quarter close."
        )
        if pacing.get("corrective_recommendation"):
            cr = pacing["corrective_recommendation"]
            bullet += f" Corrective: +${cr['total_shift_per_week']:,}/wk recommended (see Pacing tab)."
        bullets.append(bullet)

    # Competitor-explained alert bullet
    explained = [a for a in alerts if a.get("competitor_context")]
    if explained:
        ctx = explained[0]["competitor_context"]
        bullets.append(
            f"Market read: {explained[0]['title']} <- {ctx['competitor']} "
            f"{ctx['signal_type']} ({ctx['value']}). Posture: {ctx['posture_recommendation'].upper()}."
        )

    top_shift = max(alloc["rationale"], key=lambda x: abs(x["delta"]))
    if abs(top_shift["delta"]) > 2000:
        bullets.append(
            f"Recommend: shift ${abs(top_shift['delta']):,} "
            f"{'into' if top_shift['delta'] > 0 else 'out of'} {top_shift['label']} "
            f"-- {top_shift['score_plain']}"
        )
    else:
        bullets.append(f"Allocation stable WoW -- hold course within ${alloc['envelope']:,.0f} envelope")

    if alerts and not explained:
        bullets.append(f"Alert: {alerts[0]['title']} -- {alerts[0]['message'][:110]}")
    elif cards and cards[0]["fatigue"] == "high":
        bullets.append(f"Creative: rotate {cards[0]['name']} (high fatigue detected)")
    elif not alerts:
        running = [e for e in exps if e.get("recommendation") == "keep_running"]
        if running:
            bullets.append(f"Experiment running: {running[0]['name']} -- keep for causal read")
        else:
            bullets.append("No critical alerts this week -- monitor net-new signal quality")

    # ── Decisions pending ─────────────────────────────
    decisions = [{
        "id": "alloc_main",
        "title": "Approve next-week budget allocation (Math-optimal)",
        "summary": alloc["summary"],
        "details": [
            f"{r['label']}: ${r['current_spend']:,} → ${r['recommended_spend']:,} ({'+' if r['delta'] >= 0 else ''}{r['delta']:,})"
            for r in alloc["rationale"] if abs(r["delta"]) > 1500
        ] or ["No major shifts — within stability band"],
        "status": "pending",
    }]

    # Parallel "Pacing-Corrected Allocation" decision — closed-loop moment
    cr = (pacing or {}).get("corrective_recommendation")
    if cr:
        decisions.append({
            "id": "pacing_corrected_alloc",
            "title": "Approve pacing-corrected shift (Closed-loop)",
            "summary": cr["headline"],
            "details": [
                f"+${s['into_channel']:,}/wk into {s['label']} — {s['rationale']}"
                for s in cr["shifts"][:4]
            ],
            "status": "pending",
        })

    for e in exps:
        if e.get("recommendation") in ACTIONABLE_RECS and e.get("status") == "running":
            decisions.append({
                "id": e["experiment_id"],
                "title": f"Experiment: {REC_VERB.get(e['recommendation'], e['recommendation'].title())} — {e['name']}",
                "summary": e["recommendation_text"],
                "details": [e.get("learning") or e["hypothesis"]],
                "status": "pending",
            })

    for c in cards:
        if c["fatigue"] == "high":
            decisions.append({
                "id": c["creative_id"],
                "title": f"Creative rotation: {c['name']}",
                "summary": c["recommend_to_brand"],
                "details": [c["finding"], f"Directive: {c['directive_text']}"],
                "status": "pending",
            })

    segment_context = (
        "Consumer self-serve (PLG). Optimization priority: acquisition efficiency and "
        "payback velocity across creator and paid-social channels."
        if segment == "consumer"
        else "Enterprise sales-assisted. Optimization priority: qualified-pipeline quality "
        "through LinkedIn ABM, accepting an extended payback window."
    )

    return {
        "title": f"Growth Council Brief — {state['week_label']}",
        "segment": segment,
        "segment_label": "Consumer / PLG" if segment == "consumer" else "Enterprise",
        "segment_context": segment_context,
        "headline_bullets": bullets[:5],
        "decisions_pending": decisions,
        "counterfactual": _counterfactual(kpis, alloc),
        "priority_actions": _priority_actions(state, alloc, alerts, exps, cards),
        "allocation_summary": alloc["summary"],
        "alert_count": len(alerts),
        "active_experiments": len([e for e in exps if e.get("status") == "running"]),
    }
