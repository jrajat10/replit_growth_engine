"""Paid campaign intelligence — UTM decode, LP message match, performance rollup."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import config


def parse_utm_url(url: str) -> dict[str, str]:
    """Extract UTM params from a landing URL."""
    qs = parse_qs(urlparse(url).query)
    return {
        k.replace("utm_", ""): v[0]
        for k, v in qs.items()
        if k.startswith("utm_")
    }


def decode_creative_taxonomy(utm_content: str) -> dict[str, str]:
    """
    Parse Replit-style utm_content tags.
    Example: '[Image] [BuildAnythingOneSentence] [Static]'
    """
    parts = [p.strip("[] ") for p in utm_content.replace("][", "] [").split("[") if p.strip("] ")]
    out = {"raw": utm_content}
    if len(parts) >= 3:
        out["format"] = parts[0]
        out["theme"] = parts[1]
        out["type"] = parts[2]
    elif utm_content.isdigit():
        out["meta_creative_id"] = utm_content
    return out


def score_landing_match(theme: str) -> tuple[float, str]:
    """Score how well ad theme matches homepage hero (Coframe-style continuity)."""
    hp = config.HOMEPAGE_MESSAGES
    theme_lower = theme.lower()
    if "buildanything" in theme_lower or "onesentence" in theme_lower:
        return 0.95, f"Strong match: ad theme aligns with '{hp['hero']}' + one-line prompt UX"
    if "agent" in theme_lower:
        return 0.90, f"Strong match: aligns with {hp['product']} homepage section"
    if "nocode" in theme_lower or "free" in theme_lower:
        return 0.88, f"Match: '{hp['subhead']}' / '{hp['risk_reducer']}'"
    return 0.70, "Generic homepage LP — no themed continuity from utm_content"


def build_campaign_intelligence(
    perf_rows: list[dict] | None = None,
    segment: str = "consumer",
) -> dict[str, Any]:
    """Enrich known campaigns with taxonomy + sample performance."""
    perf_rows = perf_rows or []
    campaigns = []

    for c in config.PAID_CAMPAIGNS:
        if c["segment"] != segment:
            continue
        taxonomy = decode_creative_taxonomy(c["utm_content"])
        theme = taxonomy.get("theme", "")
        if theme:
            match_score, match_note = score_landing_match(theme)
        else:
            match_score = c.get("message_match_score", 0.7)
            match_note = c.get("landing_message", "")

        # Roll up meta_prospect spend as proxy if no campaign-level data
        ig_spend = sum(
            float(r["spend"]) for r in perf_rows
            if r.get("segment") == segment and r.get("channel") == "meta_prospect"
        )
        share = 0.55 if "BuildAnything" in c["name"] else 0.45

        campaigns.append({
            **c,
            "taxonomy": taxonomy,
            "message_match_score": round(match_score, 2),
            "message_match_note": match_note,
            "estimated_weekly_spend": round(ig_spend * share) if ig_spend else None,
            "learnings": _campaign_learnings(c, taxonomy),
        })

    return {
        "platform": "instagram",
        "source_medium": "ig / paid",
        "landing_page": config.HOMEPAGE_MESSAGES,
        "campaigns": campaigns,
        "taxonomy_guide": config.UTM_CONTENT_TAXONOMY,
        "insights": _aggregate_insights(campaigns),
    }


def _campaign_learnings(c: dict, taxonomy: dict) -> list[str]:
    learnings = []
    if taxonomy.get("theme") == "BuildAnythingOneSentence":
        learnings.append("Creative theme mirrors homepage one-line prompt — high message continuity")
        learnings.append("Static image format — test vs Reels/Video in campaign B")
    if taxonomy.get("meta_creative_id"):
        learnings.append("utm_content is numeric only — harder to analyze; recommend [Format][Theme][Type] naming")
    learnings.append("Both ads land on same homepage — opportunity for Coframe-style themed LP by utm_content")
    return learnings


def _aggregate_insights(campaigns: list[dict]) -> list[str]:
    if len(campaigns) < 2:
        return []
    named = [c for c in campaigns if c["taxonomy"].get("theme")]
    return [
        "Two parallel IG campaigns running — likely creative or campaign-level test",
        f"Campaign A uses structured utm_content taxonomy ({named[0]['utm_content'] if named else 'n/a'}) — best practice for reporting",
        "Campaign B uses numeric utm_content — rely on Meta Ads Manager for creative lookup",
        "Homepage emphasizes 'first prompt is free' — ensure ad copy sets credit/pricing expectations",
        "Example prompts on LP (B2B PM app, freelance portal, AI sales) = use-case hooks to test in next creative variants",
    ]
