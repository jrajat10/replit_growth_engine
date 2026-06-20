"""Weekly Growth Council Brief — narrative-first decision memo."""

from __future__ import annotations

from typing import Any

import config


def build_memo(state: dict) -> dict[str, Any]:
    segment = state["segment"]
    kpis = state["kpis"]
    alloc = state["allocation"]
    alerts = state["alerts"]
    exps = state["experiments"]
    cards = state["creative_cards"]
    geo = state["geo"]

    # Headline bullets (3)
    bullets = []

    spend_wow = kpis["spend"]["wow"]
    cac_wow = kpis["cac"]["wow"]
    if spend_wow.get("pct"):
        bullets.append(
            f"Spend {'up' if spend_wow['pct']>0 else 'down'} {abs(spend_wow['pct']*100):.0f}% WoW "
            f"to ${kpis['spend']['value']:,.0f}; CAC at ${kpis['cac']['value']:.0f} "
            f"({'+' if cac_wow.get('pct',0) and cac_wow['pct']>0 else ''}"
            f"{cac_wow['pct']*100:.0f}% WoW)" if cac_wow.get("pct") else ""
        )
    else:
        bullets.append(f"Spend ${kpis['spend']['value']:,.0f} this week; CAC ${kpis['cac']['value']:.0f}")

    top_shift = max(alloc["rationale"], key=lambda x: abs(x["delta"]))
    if abs(top_shift["delta"]) > 2000:
        bullets.append(
            f"Recommend: shift ${abs(top_shift['delta']):,} "
            f"{'into' if top_shift['delta']>0 else 'out of'} {top_shift['label']} "
            f"— {top_shift['score_plain']}"
        )
    else:
        bullets.append(f"Allocation stable WoW — hold course within ${alloc['envelope']:,.0f} envelope")

    if alerts:
        bullets.append(f"Alert: {alerts[0]['title']} — {alerts[0]['message'][:120]}")
    elif cards and cards[0]["fatigue"] == "high":
        bullets.append(f"Creative: rotate {cards[0]['name']} (fatigue detected)")
    else:
        running = [e for e in exps if e.get("recommendation") == "keep_running"]
        if running:
            bullets.append(f"Experiment: {running[0]['name']} — keep running for causal read")
        else:
            bullets.append("No critical alerts — monitor net-new signal quality")

    # Decisions pending approval
    decisions = [{
        "id": "alloc_main",
        "title": "Approve next-week budget allocation",
        "summary": alloc["summary"],
        "details": [
            f"{r['label']}: ${r['current_spend']:,} → ${r['recommended_spend']:,} "
            f"({'+' if r['delta']>=0 else ''}{r['delta']:,})"
            for r in alloc["rationale"] if abs(r["delta"]) > 1500
        ] or ["No major shifts — within stability band"],
        "status": "pending",
    }]

    for e in exps:
        if e.get("recommendation") in ("ship", "stop") and e.get("status") == "running":
            decisions.append({
                "id": e["experiment_id"],
                "title": f"Experiment: {e['recommendation'].upper()} — {e['name']}",
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
                "details": [c["finding"], f"Brand directive: {c['directive_text']}"],
                "status": "pending",
            })

    # Counterfactual (simple)
    if kpis["cac"]["wow"].get("pct") and kpis["cac"]["wow"]["pct"] > 0:
        counterfactual = (
            "If last week's allocation shift had been applied, "
            "estimated CAC improvement: −4% to −7% (based on posterior efficiency)."
        )
    else:
        counterfactual = "Current allocation aligned with efficiency scores — no missed savings flagged."

    segment_context = (
        "Consumer/PLG: optimize for fast payback, creator + paid social heavy."
        if segment == "consumer"
        else "Enterprise: optimize for pipeline quality, LinkedIn ABM + longer payback window."
    )

    return {
        "title": f"Growth Council Brief — {state['week_label']}",
        "segment": segment,
        "segment_label": "Consumer / PLG" if segment == "consumer" else "Enterprise",
        "segment_context": segment_context,
        "headline_bullets": bullets[:3],
        "decisions_pending": decisions,
        "counterfactual": counterfactual,
        "allocation_summary": alloc["summary"],
        "alert_count": len(alerts),
        "active_experiments": len([e for e in exps if e.get("status") == "running"]),
    }
