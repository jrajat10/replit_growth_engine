"""Natural language Q&A over growth state — templated, cite sources."""

from __future__ import annotations

import re
from typing import Any


def answer(question: str, state: dict, memo: dict) -> dict[str, Any]:
    q = question.lower().strip()
    segment = state["segment"]
    sources = []

    # LATAM / TikTok
    if any(w in q for w in ("latam", "latin")):
        geo = next((g for g in state["geo"] if g["geo"] == "LATAM"), None)
        exp = next((e for e in state["experiments"] if "latam" in e.get("experiment_id", "").lower()), None)
        sources.append("geo_decomposition")
        parts = []
        if geo:
            parts.append(
                f"LATAM CAC is ${geo['cac']:.0f} with ARPU multiplier {geo['arpu_multiplier']}× "
                f"(cheap CPM trap — low revenue per user)."
            )
        if exp:
            sources.append("experiment:exp_geo_holdout_latam")
            parts.append(exp.get("recommendation_text", ""))
        alloc = state["allocation"]
        tk = next((r for r in alloc["rationale"] if r["channel"] == "tiktok_creator"), None)
        if tk and "tiktok" in q:
            sources.append("allocation")
            parts.append(
                f"TikTok recommended spend: ${tk['recommended_spend']:,} "
                f"(delta {tk['delta']:+,}). LTV multiplier: {tk['ltv_multiplier']}× — "
                f"{tk['ltv_explanation']}"
            )
        return {
            "answer": " ".join(parts) or "LATAM data not available for this segment.",
            "sources": sources,
        }

    # TikTok / creator
    if any(w in q for w in ("tiktok", "creator")):
        sources.append("allocation")
        r = next((x for x in state["allocation"]["rationale"] if "tiktok" in x["channel"]), None)
        card = next((c for c in state["creative_cards"] if "tiktok" in c["channel"]), None)
        parts = []
        if r:
            parts.append(
                f"TikTok/Creator: spend ${r['current_spend']:,} → recommend ${r['recommended_spend']:,}. "
                f"{r['score_plain']}"
            )
        if card:
            sources.append(f"creative:{card['creative_id']}")
            parts.append(f"Creative '{card['name']}': {card['fatigue_message']}. {card['recommend_to_brand']}")
        return {"answer": " ".join(parts), "sources": sources}

    # Allocation / why recommend
    if any(w in q for w in ("allocat", "recommend", "shift", "budget", "why")):
        sources.append("allocation")
        alloc = state["allocation"]
        shifts = [r for r in alloc["rationale"] if abs(r["delta"]) > 2000]
        if shifts:
            top = max(shifts, key=lambda x: abs(x["delta"]))
            ans = (
                f"{alloc['summary']} Top move: {top['label']} "
                f"{'+' if top['delta']>0 else ''}{top['delta']:,}. "
                f"Reason: {top['score_plain']}. "
                f"Method: rank channels by (net-new per $ × LTV multiplier), "
                f"fill budget within ${alloc['envelope']:,.0f} guardrails."
            )
        else:
            ans = alloc["summary"]
        return {"answer": ans, "sources": sources}

    # Attribution / retargeting
    if any(w in q for w in ("attribution", "retarget", "last-touch", "last touch", "markov")):
        sources.append("attribution")
        attr = state["attribution"]
        return {
            "answer": attr.get("retargeting_diagnostic", {}).get("plain_english", attr.get("simple_explanation", "")),
            "sources": sources,
        }

    # Experiments / incrementality / holdout
    if any(w in q for w in ("experiment", "holdout", "incremental", "causal", "a/b", "ab test")):
        sources.append("experiments")
        exps = state["experiments"]
        if not exps:
            return {"answer": "No experiments for this segment.", "sources": sources}
        lines = [f"{e['name']}: {e['recommendation_text']}" for e in exps[:3]]
        return {
            "answer": " ".join(lines),
            "sources": sources + [e["experiment_id"] for e in exps[:3]],
        }

    # Creative / fatigue / brand
    if any(w in q for w in ("creative", "fatigue", "brand", "rotate")):
        sources.append("creative_cards")
        cards = state["creative_cards"]
        tired = [c for c in cards if c["fatigue"] != "low"]
        if tired:
            c = tired[0]
            return {
                "answer": f"{c['name']}: {c['insight_summary']} Handoff to Brand: {c['recommend_to_brand']}",
                "sources": [f"creative:{c['creative_id']}"],
            }
        return {"answer": "All creatives stable this week.", "sources": sources}

    # CAC / payback
    if any(w in q for w in ("cac", "payback", "ltv")):
        sources.append("kpis")
        k = state["kpis"]
        return {
            "answer": (
                f"CAC ${k['cac']['value']:.0f} ({k['cac']['fmt_wow']} WoW), "
                f"target ceiling ${k['cac']['target']}. "
                f"LTV:CAC {k['ltv_cac']['value']:.1f}× (target {k['ltv_cac']['target']}×). "
                f"Payback {k['payback_months']['value']:.1f}mo vs target {k['payback_months']['target']}mo."
            ),
            "sources": sources,
        }

    # Default — memo summary
    sources.append("decision_memo")
    return {
        "answer": (
            f"Weekly brief for {memo['segment_label']}: "
            + " | ".join(memo["headline_bullets"][:2])
            + f" Try asking about LATAM, TikTok, allocation, experiments, or creative fatigue."
        ),
        "sources": sources,
    }
