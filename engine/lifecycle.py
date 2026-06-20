"""Lifecycle model — LTV multipliers fed into allocation (no separate lifecycle dashboard in v0)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import config

# Modeled activation quality by channel (from lifecycle funnel: acquired→activated→monetized)
# Higher = better downstream LTV per conversion
CHANNEL_LTV_MULTIPLIER = {
    "consumer": {
        "google_brand": 0.85,       # lots of returning users
        "google_nonbrand": 1.25,    # high intent
        "meta_prospect": 1.05,
        "meta_retarget": 0.70,      # low net-new quality
        "tiktok_creator": 0.75,     # cheap CPM but weaker activation
        "youtube": 1.10,
        "reddit_test": 0.90,
    },
    "enterprise": {
        "google_brand": 0.95,
        "google_nonbrand": 1.15,
        "linkedin_abm": 1.35,
        "linkedin_retarget": 0.80,
        "meta_prospect": 0.85,
        "youtube": 1.05,
    },
}


def geo_ltv_adjustment(geo: str) -> float:
    return config.GEO_ARPU_MULTIPLIER.get(geo, 1.0)


def compute_channel_ltv_multipliers(
    perf_rows: list[dict],
    segment: str,
) -> dict[str, dict]:
    """
    Returns per-channel LTV multiplier used by the allocator.
    Combines lifecycle quality score × observed geo ARPU mix.
    """
    base = CHANNEL_LTV_MULTIPLIER.get(segment, {})
    spend_by_ch_geo: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for r in perf_rows:
        if r["segment"] != segment:
            continue
        spend_by_ch_geo[r["channel"]][r["geo"]] += float(r["spend"])

    out = {}
    for channel in config.CHANNELS.get(segment, []):
        quality = base.get(channel, 1.0)
        geo_spend = spend_by_ch_geo.get(channel, {})
        total = sum(geo_spend.values()) or 1
        geo_mix_adj = sum(
            (amt / total) * geo_ltv_adjustment(geo)
            for geo, amt in geo_spend.items()
        )
        effective = quality * geo_mix_adj
        out[channel] = {
            "quality_score": round(quality, 2),
            "geo_arpu_mix": round(geo_mix_adj, 2),
            "ltv_multiplier": round(effective, 2),
            "explanation": (
                f"Lifecycle quality {quality:.2f} × geo ARPU mix {geo_mix_adj:.2f} "
                f"= {effective:.2f}× effective LTV"
            ),
        }
    return out
