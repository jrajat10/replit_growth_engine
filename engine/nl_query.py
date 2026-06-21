"""Natural language Q&A — 20+ pattern coverage with cited sources."""

from __future__ import annotations
import re
from typing import Any


def _q(question: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", question.lower().strip())


def answer(question: str, state: dict, memo: dict) -> dict[str, Any]:
    q = _q(question)
    kpis = state["kpis"]
    alloc = state["allocation"]
    geo = state["geo"]
    exps = state["experiments"]
    cards = state["creative_cards"]
    alerts = state["alerts"]
    attr = state["attribution"]

    # ── 0a. FUNNEL / QCAC / ACTIVATION / FREE-TO-PAID ──
    if any(w in q for w in ["funnel", "qcac", "q cac", "quality cac", "activat", "free to paid", "free-to-paid", "paid conversion", "prompt start"]):
        f = state.get("funnel", {})
        fc = state.get("funnel_forecast", {})
        if not f:
            return {"answer": "Funnel data not loaded.", "sources": ["funnel"]}
        forecast_str = ""
        if fc.get("available"):
            forecast_str = f" Forecast next paid cohort: ~{fc['total_forecast_paid']} (cohort method: {fc['method']})."
        return {
            "answer": (
                f"Funnel: CAC ${f['cac']:,.0f} vs qCAC ${f['qcac']:,.0f} ({f['qcac_to_cac_ratio']}× CAC). "
                f"Activation {f['activation_rate']}% (signup -> first published deploy in 7d). "
                f"Free->Paid {f['free_to_paid_rate']}% of activated. "
                f"Prompt-start rate {f['prompt_start_rate']}%.{forecast_str} "
                f"Allocator optimizes on signups; funnel keeps us honest on quality."
            ),
            "sources": ["funnel", "funnel_forecast"],
        }

    # ── 0b. COMPETITION / LOVABLE / V0 / BOLT / MARKET ──
    if any(w in q for w in ["competitor", "competition", "lovable", "v0", "bolt", "base44", "market read", "impression share"]):
        comp = state.get("competition", {})
        sigs = comp.get("recent_signals", [])
        if not sigs:
            return {"answer": "No active competitor signals this week.", "sources": ["competition"]}
        parts = [
            f"{s['competitor_id']} {s['signal_type']} ({s['value']}, conf {s['confidence']*100:.0f}%): {s['implication']}"
            for s in sigs[:3]
        ]
        explained = [a for a in alerts if a.get("competitor_context")]
        if explained:
            ctx = explained[0]["competitor_context"]
            parts.append(f"This week: {explained[0]['title']} -> {ctx['competitor']} {ctx['signal_type']} ({ctx['value']}). Posture: {ctx['posture_recommendation'].upper()}.")
        return {"answer": " | ".join(parts), "sources": ["competition"] + [s["signal_id"] for s in sigs[:3]]}

    # ── 0c. ROADMAP / WHAT'S NEXT / WHAT'S COMING ───────
    if any(w in q for w in ["roadmap", "what s next", "whats next", "what s coming", "whats coming", "next version", "next milestone"]) or re.search(r"\bv1\b|\bv1 5\b|\bv2\b", q):
        rm = state.get("roadmap", {})
        versions = rm.get("versions", [])
        if not versions:
            return {"answer": "Roadmap not loaded.", "sources": ["roadmap"]}
        parts = [f"{v['version']} [{v['status']}]: {v['title']}" for v in versions]
        return {"answer": " | ".join(parts) + f" -- {rm.get('tagline', '')}", "sources": ["roadmap"]}

    # ── 1. TOP PRIORITY / FOCUS / WHAT TO DO ──────────
    if any(w in q for w in ["focus", "priority", "what to do", "this week", "action", "most important", "where to start", "top 3"]):
        if not any(w in q for w in ["allocat", "budget"]):
            actions = memo.get("priority_actions", [])
            if actions:
                parts = [f"{i+1}. {a['action']} [{a['owner']}] — {a['reason']}" for i, a in enumerate(actions)]
                return {"answer": " | ".join(parts), "sources": ["decision_memo"]}
            return {"answer": " | ".join(memo.get("headline_bullets", [])[:2]), "sources": ["decision_memo"]}

    # ── 2. ALERTS / PROBLEMS / WHAT'S WRONG ──────────
    if any(w in q for w in ["wrong", "problem", "issue", "concern", "risk", "bad", "alert", "warning", "flag", "urgent"]):
        if not alerts:
            return {"answer": "No critical alerts this week. All key metrics are within targets.", "sources": ["alerts"]}
        parts = [f"[{a['severity'].upper()}] {a['title']}: {a['message']}" for a in alerts[:3]]
        return {"answer": " | ".join(parts), "sources": ["alerts"]}

    # ── 3. WHAT'S WORKING / BEST CHANNEL ─────────────
    if any(w in q for w in ["working", "performing well", "best channel", "strongest", "winner", "what works", "top channel"]):
        scored = sorted(
            alloc["rationale"],
            key=lambda r: (r.get("ltv_multiplier", 1) / max(float(r["cac"]), 1)),
            reverse=True,
        )
        top = scored[0] if scored else None
        if top:
            return {
                "answer": (
                    f"Highest efficiency: {top['label']} — CAC ${top['cac']}, "
                    f"LTV mult {top['ltv_multiplier']}×. {top['score_plain']} "
                    f"Recommended spend: ${top['recommended_spend']:,}."
                ),
                "sources": ["allocation", "performance"],
            }

    # ── 4. WORST / UNDERPERFORMING CHANNEL ───────────
    if any(w in q for w in ["worst", "underperform", "lowest", "poor", "drag", "weakest", "cut", "drop", "pause", "kill"]):
        if "latam" not in q and "tiktok" not in q:
            scored = sorted(
                alloc["rationale"],
                key=lambda r: (r.get("ltv_multiplier", 1) / max(float(r["cac"]), 1)),
            )
            worst = scored[0] if scored else None
            if worst:
                return {
                    "answer": (
                        f"Lowest efficiency: {worst['label']} — CAC ${worst['cac']}, "
                        f"LTV mult {worst['ltv_multiplier']}×. {worst['score_plain']}"
                    ),
                    "sources": ["allocation"],
                }

    # ── 5. LATAM / GEO / REGION ──────────────────────
    if any(w in q for w in ["latam", "latin", "geo", "region", "geography", "canada", "us west", "us east"]):
        sources = ["geo_decomposition"]
        parts = []
        if "latam" in q or "latin" in q:
            latam = next((g for g in geo if g["geo"] == "LATAM"), None)
            exp = next((e for e in exps if "latam" in e.get("experiment_id", "").lower()), None)
            if latam:
                parts.append(
                    f"LATAM: ${latam['spend']:,} spend, CAC ${latam['cac']:.0f}, "
                    f"ARPU mult {latam['arpu_multiplier']}× vs US West 1.15×. "
                    "Cheap CPM does not offset low LTV — net adjusted efficiency is underwater."
                )
            if exp:
                sources.append(f"experiment:{exp['experiment_id']}")
                parts.append(f"Geo holdout result: {exp['recommendation_text']}")
        else:
            for g in geo:
                flag_str = f" ⚠ {g['flag']}" if g.get("flag") else ""
                parts.append(f"{g['geo']}: CAC ${g['cac']:.0f}, ARPU {g['arpu_multiplier']}×{flag_str}")
        if "tiktok" in q:
            tk = next((r for r in alloc["rationale"] if "tiktok" in r["channel"]), None)
            if tk:
                sources.append("allocation")
                parts.append(
                    f"TikTok in this context: ${tk['current_spend']:,} → ${tk['recommended_spend']:,} "
                    f"(Δ{tk['delta']:+,}). {tk['score_plain']}"
                )
        return {"answer": " | ".join(parts) or "No geo data available.", "sources": sources}

    # ── 6. TIKTOK / CREATOR ───────────────────────────
    if any(w in q for w in ["tiktok", "creator", "ugc"]):
        sources = ["allocation"]
        parts = []
        r = next((x for x in alloc["rationale"] if "tiktok" in x["channel"]), None)
        card = next((c for c in cards if "tiktok" in c["channel"]), None)
        if r:
            parts.append(
                f"TikTok/Creator: ${r['current_spend']:,} → ${r['recommended_spend']:,} "
                f"(Δ{r['delta']:+,}). {r['score_plain']}"
            )
        if card:
            sources.append(f"creative:{card['creative_id']}")
            parts.append(f"Creative '{card['name']}': {card['fatigue_message']}. {card['recommend_to_brand']}")
        return {"answer": " | ".join(parts) or "TikTok not in this segment's channel mix.", "sources": sources}

    # ── 7. GOOGLE ─────────────────────────────────────
    if "google" in q:
        sources = ["allocation"]
        parts = []
        for ch in ["google_brand", "google_nonbrand"]:
            r = next((x for x in alloc["rationale"] if x["channel"] == ch), None)
            if r:
                parts.append(
                    f"{r['label']}: ${r['current_spend']:,} → ${r['recommended_spend']:,} "
                    f"(Δ{r['delta']:+,}). {r['score_plain']}"
                )
        return {"answer": " | ".join(parts) or "No Google data.", "sources": sources}

    # ── 8. META / FACEBOOK ────────────────────────────
    if any(w in q for w in ["meta", "facebook", "instagram", "utm", "ig ad"]):
        sources = ["allocation", "paid_campaigns"]
        pc = state.get("paid_campaigns", {})
        parts = []
        for c in pc.get("campaigns", []):
            parts.append(
                f"{c['name']}: utm_content={c['utm_content']}, "
                f"message match {c['message_match_score']*100:.0f}%"
            )
        meta = [r for r in alloc["rationale"] if "meta" in r["channel"]]
        for r in meta:
            parts.append(
                f"{r['label']}: ${r['current_spend']:,} → ${r['recommended_spend']:,} (Δ{r['delta']:+,})"
            )
        return {"answer": " | ".join(parts) or "No Meta/IG data.", "sources": sources}

    # ── 9. LINKEDIN ───────────────────────────────────
    if "linkedin" in q:
        sources = ["allocation"]
        li = [r for r in alloc["rationale"] if "linkedin" in r["channel"]]
        if not li:
            return {"answer": "LinkedIn is not in this segment's channel mix. Switch to Enterprise segment.", "sources": sources}
        parts = [
            f"{r['label']}: ${r['current_spend']:,} → ${r['recommended_spend']:,} "
            f"(Δ{r['delta']:+,}). {r['score_plain']}"
            for r in li
        ]
        return {"answer": " | ".join(parts), "sources": sources}

    # ── 10. ALLOCATION / BUDGET / WHY RECOMMEND ───────
    if any(w in q for w in ["allocat", "budget", "shift", "where to spend", "envelope"]):
        sources = ["allocation"]
        shifts = [r for r in alloc["rationale"] if abs(r["delta"]) > 2000]
        if shifts:
            top = max(shifts, key=lambda x: abs(x["delta"]))
            ans = (
                f"{alloc['summary']} Top move: {top['label']} Δ{top['delta']:+,}. "
                f"Reason: {top['score_plain']}. "
                f"Method: channels ranked by net-new per $ × LTV multiplier, "
                f"filled within ${alloc['envelope']:,} guardrails."
            )
        else:
            ans = alloc["summary"]
        return {"answer": ans, "sources": sources}

    # ── 11. ATTRIBUTION / RETARGETING ─────────────────
    if any(w in q for w in ["attribution", "retarget", "last touch", "last-touch", "markov", "credit", "overcredit"]):
        sources = ["attribution"]
        diag = attr.get("retargeting_diagnostic", {})
        return {
            "answer": (
                f"{attr.get('simple_explanation', '')} "
                f"Retargeting diagnostic: {diag.get('plain_english', '')} "
                f"{attr.get('action', '')}"
            ).strip(),
            "sources": sources,
        }

    # ── 12. EXPERIMENTS / INCREMENTALITY ──────────────
    if any(w in q for w in ["experiment", "holdout", "incremental", "causal", "a b test", "ab test", "lift", "p value", "statistical", "test"]):
        sources = ["experiments"]
        if not exps:
            return {"answer": "No experiments running for this segment.", "sources": sources}
        parts = [
            f"{e['name']} [{e['type']}]: lift {e['lift_pct']}%, p={e['p_value']} → {e['recommendation_text']}"
            for e in exps[:3]
        ]
        return {"answer": " | ".join(parts), "sources": sources + [e["experiment_id"] for e in exps[:2]]}

    # ── 13. CREATIVE / FATIGUE / BRAND ────────────────
    if any(w in q for w in ["creative", "fatigue", "ad creative", "copy", "brand", "rotate", "directive"]):
        sources = ["creative_cards"]
        tired = [c for c in cards if c["fatigue"] != "low"]
        if tired:
            c = tired[0]
            return {
                "answer": (
                    f"{c['name']} ({c['channel_label']}): {c['insight_summary']} "
                    f"Brand handoff: {c['recommend_to_brand']}"
                ),
                "sources": [f"creative:{c['creative_id']}"],
            }
        return {"answer": f"All {len(cards)} creatives show low fatigue this week.", "sources": sources}

    # ── 14. CAC / PAYBACK / LTV ───────────────────────
    if any(w in q for w in ["cac", "payback", "ltv", "cost per", "lifetime value", "unit economics"]):
        sources = ["kpis"]
        above_target = kpis["payback_months"]["value"] > kpis["payback_months"]["target"]
        return {
            "answer": (
                f"CAC ${kpis['cac']['value']:.0f} ({kpis['cac']['fmt_wow']} WoW, ceiling ${kpis['cac']['target']}). "
                f"LTV:CAC {kpis['ltv_cac']['value']:.1f}× (target {kpis['ltv_cac']['target']}×). "
                f"Payback {kpis['payback_months']['value']:.1f}mo (target {kpis['payback_months']['target']}mo). "
                + ("⚠ Payback drifting above target — review channel mix." if above_target else "Payback on track.")
            ),
            "sources": sources,
        }

    # ── 15. NET-NEW / SIGNAL QUALITY ──────────────────
    if any(w in q for w in ["net new", "net-new", "signal", "signal quality", "new user", "new conversion", "exclusion"]):
        pct = kpis["net_new_pct"]["value"] * 100
        warn = " ⚠ Below 60% threshold — retargeting inflating counts; optimizer efficiency scores are biased upward." if pct < 60 else " Signal healthy."
        return {
            "answer": f"Net-new conversion rate: {pct:.0f}%.{warn} Optimizer uses net-new only — raw conversion count is not the optimization signal.",
            "sources": ["kpis", "attribution"],
        }

    # ── 16. SPEND / TOTAL ─────────────────────────────
    if any(w in q for w in ["spend", "total spend", "how much", "weekly spend"]):
        return {
            "answer": (
                f"Total spend: ${kpis['spend']['value']:,.0f} ({kpis['spend']['fmt_wow']} WoW). "
                f"Envelope: ${alloc['envelope']:,}. {alloc['summary']}"
            ),
            "sources": ["kpis", "allocation"],
        }

    # ── 17. YOUTUBE ──────────────────────────────────────
    if "youtube" in q:
        r = next((x for x in alloc["rationale"] if "youtube" in x["channel"]), None)
        card = next((c for c in cards if "youtube" in c["channel"]), None)
        parts, sources = [], ["allocation"]
        if r:
            parts.append(
                f"YouTube: ${r['current_spend']:,} → ${r['recommended_spend']:,} "
                f"(Δ{r['delta']:+,}). {r['score_plain']}"
            )
        if card:
            sources.append(f"creative:{card['creative_id']}")
            parts.append(f"Creative '{card['name']}': {card['fatigue_message']}. {card['recommend_to_brand']}")
        return {"answer": " | ".join(parts) or "YouTube not in this segment's channel mix.", "sources": sources}

    # ── 18. REDDIT ───────────────────────────────────────
    if "reddit" in q:
        r = next((x for x in alloc["rationale"] if "reddit" in x["channel"]), None)
        if not r:
            return {
                "answer": "Reddit is not in this segment's channel mix. Switch to Consumer / PLG to see Reddit (Test) data.",
                "sources": ["allocation"],
            }
        return {
            "answer": (
                f"Reddit (Test channel): ${r['current_spend']:,} → ${r['recommended_spend']:,} "
                f"(Δ{r['delta']:+,}). {r['score_plain']}"
            ),
            "sources": ["allocation"],
        }

    # ── 19. ALL CHANNELS / CHANNEL MIX ──────────────────
    if any(w in q for w in ["all channel", "channel mix", "every channel", "channel breakdown", "channel summary", "full channel"]):
        ranked = sorted(
            alloc["rationale"],
            key=lambda r: r.get("ltv_multiplier", 1) / max(float(r["cac"]), 1),
            reverse=True,
        )
        parts = [
            f"{r['label']}: ${r['recommended_spend']:,} recommended | CAC ${r['cac']}"
            for r in ranked
        ]
        return {
            "answer": "Channel mix ranked by efficiency: " + " | ".join(parts),
            "sources": ["allocation"],
        }

    # ── 20. OVERVIEW / SUMMARY ───────────────────────────
    if any(w in q for w in ["overview", "how are we", "how is everything", "overall", "brief me", "summarize", "give me a summary", "what can you tell"]):
        top = max(alloc["rationale"], key=lambda r: r.get("ltv_multiplier", 1) / max(float(r["cac"]), 1))
        worst = min(alloc["rationale"], key=lambda r: r.get("ltv_multiplier", 1) / max(float(r["cac"]), 1))
        running = [e for e in exps if e.get("status") == "running"]
        alert_str = f" ⚠ {len(alerts)} alert(s) — {alerts[0]['title']}." if alerts else " No critical alerts."
        top_action = memo["priority_actions"][0]["action"] if memo.get("priority_actions") else "see brief"
        return {
            "answer": (
                f"{memo['segment_label']} | {state['week_label']} | "
                f"Spend ${kpis['spend']['value']:,.0f} ({kpis['spend']['fmt_wow']} WoW) · "
                f"CAC ${kpis['cac']['value']:.0f} vs ${kpis['cac']['target']} ceiling · "
                f"LTV:CAC {kpis['ltv_cac']['value']:.1f}× (target {kpis['ltv_cac']['target']}×).{alert_str} "
                f"Best channel: {top['label']} (CAC ${top['cac']}). "
                f"Lowest efficiency: {worst['label']} (CAC ${worst['cac']}). "
                f"{len(running)} experiment(s) running. Top action: {top_action}."
            ),
            "sources": ["kpis", "allocation", "decision_memo"],
        }

    # ── DEFAULT ────────────────────────────────────────
    top = max(alloc["rationale"], key=lambda r: r.get("ltv_multiplier", 1) / max(float(r["cac"]), 1))
    return {
        "answer": (
            f"I have this week's {memo['segment_label']} data — "
            f"${kpis['spend']['value']:,.0f} spend, CAC ${kpis['cac']['value']:.0f} "
            f"(ceiling ${kpis['cac']['target']}), LTV:CAC {kpis['ltv_cac']['value']:.1f}×. "
            f"Best channel: {top['label']} at CAC ${top['cac']}. "
            "Ask: top priority · alerts · best/worst channel · overview · "
            "LATAM · TikTok · Google · Meta · LinkedIn · YouTube · Reddit · "
            "CAC · payback · experiments · creative fatigue · channel mix · attribution · net-new"
        ),
        "sources": ["decision_memo", "kpis"],
    }
