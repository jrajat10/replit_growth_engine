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

# Marginal-returns assumption: a channel's per-dollar efficiency decays as spend
# is pushed above its current (proven) level. Used by the allocator so the
# 50,001st dollar is not valued like the first. Higher = faster decay.
SATURATION_EXPONENT = 1.0

FINANCE_GUARDRAILS = {
    "consumer": {
        "weekly_envelope": 320_000,
        "min_channel_spend": 5_000,
        "max_channel_pct": 0.35,
        "max_weekly_shift_pct": 0.15,
        "cac_ceiling": 85,
        "payback_target_months": 6,
        "ltv_cac_target": 3.0,
    },
    "enterprise": {
        "weekly_envelope": 170_000,
        "min_channel_spend": 8_000,
        "max_channel_pct": 0.40,
        "max_weekly_shift_pct": 0.12,
        "cac_ceiling": 650,
        "payback_target_months": 14,
        "ltv_cac_target": 4.0,
    },
}

BRAND_DIRECTIVES = {
    "speed_demo": "Show idea → live app in under 2 minutes",
    "no_code_promise": "No coding needed — plain English in, app out",
    "enterprise_proof": "Logo grid + customer proof (Duolingo, Coinbase)",
    "creator_ugc": "Authentic creator voice, not polished ad",
    "build_one_sentence": "Build anything in one sentence — matches homepage prompt UX",
    "first_prompt_free": "Your first prompt is free — no credit consumption",
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

# ── Pacing & quarterly targets ──────────────────────────────────────
# Q3 2026: 13 weeks starting 2026-04-07. Latest sample data week is W11.
QUARTER_LABEL = "Q3 2026"
QUARTER_START = "2026-04-14"  # Monday W1 (latest sample week lands ~W10, 3 weeks left)
QUARTER_WEEKS = 13

# Seasonal pacing curve — channels ramp toward an offline event
# (e.g. ReplitCON) in W7, then taper to quarter close. Weights sum-normalized.
# Drives both planned-spend distribution and target-signup distribution.
PACING_CURVE_RAW = [
    0.060,  # W1
    0.063,  # W2
    0.070,  # W3
    0.080,  # W4
    0.095,  # W5
    0.110,  # W6
    0.130,  # W7  ← peak: ReplitCON / offline event
    0.110,  # W8
    0.090,  # W9
    0.075,  # W10
    0.065,  # W11
    0.060,  # W12
    0.055,  # W13 (quarter close)
]
_total = sum(PACING_CURVE_RAW)
PACING_CURVE = [w / _total for w in PACING_CURVE_RAW]
PACING_EVENT_WEEK = 7
PACING_EVENT_NAME = "ReplitCON (offline event, ramp peak)"

# Top-line targets — set by Finance + GTM leadership.
# Consumer = ARR-driven self-serve. Enterprise = pipeline-driven sales-assisted.
QUARTERLY_TARGETS = {
    "consumer": {
        "type": "arr_and_subs",
        # Sample-data scale. In production with real warehouse volume the target
        # is $5M+ ARR/Q. ARR target is editable in the UI for sensitivity.
        "arr_target_usd": 1_840_000,
        "arr_target_production": 5_000_000,    # Production-scale reference
        "consumer_arpu_annual": 240,           # $20/mo Core plan
        "free_to_paid_assumption": 0.20,       # measured activated->paid; editable in UI
        "activation_rate_assumption": 0.42,    # measured; editable in UI
        # Derived in pacing.py: subs target, signup target, channel targets
        "label": "$1.84M ARR / Q3 (sample scale)",
    },
    "enterprise": {
        "type": "pipeline",
        # Qualified pipeline $ generated per paid-acquisition signup. Must exceed
        # blended CAC for healthy economics (here ~$1.5k vs ~$560 CAC ≈ 2.7×).
        "pipeline_target_usd": 6_500_000,
        "pipeline_target_production": 20_000_000,
        "pipeline_value_per_signup": 1_500,
        "label": "$6.5M Pipeline / Q3 (sample scale)",
    },
}

# Landing page message map (for ad→LP continuity scoring)
HOMEPAGE_MESSAGES = {
    "hero": "What will you build?",
    "subhead": "Turn ideas into apps in minutes — no coding needed",
    "risk_reducer": "Your first prompt is free. No credit consumption.",
    "product": "Agent 4",
    "example_prompts": [
        "B2B project management app",
        "Freelance client portal",
        "AI sales assistant",
    ],
}

# Captured from live Instagram ads (Jun 2026)
PAID_CAMPAIGNS = [
    {
        "campaign_id": "120246121361820716",
        "name": "IG — Build Anything One Sentence (Static Image)",
        "channel": "meta_prospect",
        "platform": "instagram",
        "segment": "consumer",
        "utm_source": "ig",
        "utm_medium": "paid",
        "utm_campaign": "120246121361820716",
        "utm_content": "[Image] [BuildAnythingOneSentence] [Static]",
        "utm_term": "120246121362130716",
        "creative_format": "image",
        "creative_theme": "BuildAnythingOneSentence",
        "creative_type": "static",
        "landing_url": "https://replit.com/",
        "landing_message": "What will you build? — one-sentence prompt → app",
        "message_match_score": 0.95,
        "status": "active",
    },
    {
        "campaign_id": "120247078747270716",
        "name": "IG — Prospecting variant B",
        "channel": "meta_prospect",
        "platform": "instagram",
        "segment": "consumer",
        "utm_source": "ig",
        "utm_medium": "paid",
        "utm_campaign": "120247078747270716",
        "utm_content": "120247078898840716",
        "utm_term": "120247078880210716",
        "creative_format": "unknown",
        "creative_theme": "unknown",
        "creative_type": "unknown",
        "landing_url": "https://replit.com/",
        "landing_message": "Generic homepage — no utm_content theme tag",
        "message_match_score": 0.70,
        "status": "active",
    },
]

UTM_CONTENT_TAXONOMY = {
    "format": ["Image", "Video", "Carousel", "Reels"],
    "theme": [
        "BuildAnythingOneSentence",
        "Agent4",
        "FirstPromptFree",
        "NoCodingNeeded",
        "B2BProjectManagement",
    ],
    "type": ["Static", "UGC", "Motion"],
}
