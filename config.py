"""Growth engine configuration — AMER scope, segments, channels, guardrails."""

SEGMENTS = ("consumer", "enterprise")

GEOS = ("US_W", "US_E", "US_C", "CA", "LATAM")

CHANNELS = {
    "consumer": [
        "google_brand",
        "google_nonbrand",
        "meta_prospect",
        "meta_retarget",
        "tiktok_creator",
        "youtube",
        "reddit_test",
    ],
    "enterprise": [
        "google_brand",
        "google_nonbrand",
        "linkedin_abm",
        "linkedin_retarget",
        "meta_prospect",
        "youtube",
    ],
}

CHANNEL_LABELS = {
    "google_brand": "Google Brand",
    "google_nonbrand": "Google Non-Brand",
    "meta_prospect": "Meta Prospecting",
    "meta_retarget": "Meta Retargeting",
    "tiktok_creator": "TikTok / Creator",
    "youtube": "YouTube",
    "reddit_test": "Reddit (Test)",
    "linkedin_abm": "LinkedIn ABM",
    "linkedin_retarget": "LinkedIn Retargeting",
}

# Finance guardrails — allocator optimizes WITHIN these bounds
FINANCE_GUARDRAILS = {
    "consumer": {
        "weekly_envelope": 420_000,
        "min_channel_spend": 5_000,
        "max_channel_pct": 0.35,
        "max_weekly_shift_pct": 0.15,
        "cac_ceiling": 85,
        "payback_target_months": 6,
        "ltv_cac_target": 3.0,
    },
    "enterprise": {
        "weekly_envelope": 180_000,
        "min_channel_spend": 8_000,
        "max_channel_pct": 0.40,
        "max_weekly_shift_pct": 0.12,
        "cac_ceiling": 450,
        "payback_target_months": 14,
        "ltv_cac_target": 4.0,
    },
}

# Brand-approved creative directives (app tests; does not generate copy)
BRAND_DIRECTIVES = {
    "speed_demo": "Show idea → live app in under 2 minutes",
    "no_code_promise": "No coding needed — plain English in, app out",
    "enterprise_proof": "Logo grid + customer proof (Duolingo, Coinbase)",
    "creator_ugc": "Authentic creator voice, not polished ad",
}

GEO_ARPU_MULTIPLIER = {
    "US_W": 1.15,
    "US_E": 1.10,
    "US_C": 1.00,
    "CA": 0.95,
    "LATAM": 0.45,
}

DATA_SOURCE = "SAMPLE"
DATA_SOURCE_LABEL = "SAMPLE — not connected to live warehouse"
