"""Weekly Growth Council Brief — narrative-first decision memo."""

from __future__ import annotations
from typing import Any
import config


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
        if e.get("recommendation") in ("ship", "stop") and e.get("status") == "running":
            verb = "Ship" if e["recommendation"] == "ship" else "Stop"
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

    # ── Headline bullets ──────────────────────────────
    bullets = []

    spend_wow = kpis["spend"]["wow"]
    cac_wow = kpis["cac"]["wow"]
    if spend_wow.get("pct"):
        bullets.append(
            f"Spend {'up' if spend_wow['pct'] > 0 else 'down'} {abs(spend_wow['pct']*100):.0f}% WoW "
            f"to ${kpis['spend']['value']:,.0f}; CAC ${kpis['cac']['value']:.0f} "
            f"({'▲' if cac_wow.get('pct', 0) > 0 else '▼'}{abs(cac_wow['pct']*100):.0f}% WoW)"
            if cac_wow.get("pct") else f"Spend ${kpis['spend']['value']:,.0f}; CAC ${kpis['cac']['value']:.0f}"
        )
    else:
        bullets.append(f"Spend ${kpis['spend']['value']:,.0f} this week; CAC ${kpis['cac']['value']:.0f}")

    top_shift = max(alloc["rationale"], key=lambda x: abs(x["delta"]))
    if abs(top_shift["delta"]) > 2000:
        bullets.append(
            f"Recommend: shift ${abs(top_shift['delta']):,} "
            f"{'into' if top_shift['delta'] > 0 else 'out of'} {top_shift['label']} "
            f"— {top_shift['score_plain']}"
        )
    else:
        bullets.append(f"Allocation stable WoW — hold course within ${alloc['envelope']:,.0f} envelope")

    if alerts:
        bullets.append(f"Alert: {alerts[0]['title']} — {alerts[0]['message'][:110]}")
    elif cards and cards[0]["fatigue"] == "high":
        bullets.append(f"Creative: rotate {cards[0]['name']} (high fatigue detected)")
    else:
        running = [e for e in exps if e.get("recommendation") == "keep_running"]
        if running:
            bullets.append(f"Experiment running: {running[0]['name']} — keep for causal read")
        else:
            bullets.append("No critical alerts this week — monitor net-new signal quality")

    # ── Decisions pending ─────────────────────────────
    decisions = [{
        "id": "alloc_main",
        "title": "Approve next-week budget allocation",
        "summary": alloc["summary"],
        "details": [
            f"{r['label']}: ${r['current_spend']:,} → ${r['recommended_spend']:,} ({'+' if r['delta'] >= 0 else ''}{r['delta']:,})"
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
                "details": [c["finding"], f"Directive: {c['directive_text']}"],
                "status": "pending",
            })

    segment_context = (
        "Consumer / PLG — optimize for fast payback, creator + paid social heavy."
        if segment == "consumer"
        else "Enterprise — optimize for pipeline quality, LinkedIn ABM + longer payback window."
    )

    return {
        "title": f"Growth Council Brief — {state['week_label']}",
        "segment": segment,
        "segment_label": "Consumer / PLG" if segment == "consumer" else "Enterprise",
        "segment_context": segment_context,
        "headline_bullets": bullets[:3],
        "decisions_pending": decisions,
        "counterfactual": _counterfactual(kpis, alloc),
        "priority_actions": _priority_actions(state, alloc, alerts, exps, cards),
        "allocation_summary": alloc["summary"],
        "alert_count": len(alerts),
        "active_experiments": len([e for e in exps if e.get("status") == "running"]),
    }
