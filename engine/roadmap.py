"""Roadmap surface — v0 / v1 / v1.5 / v2 shipped to landing + cockpit."""

ROADMAP = [
    {
        "version": "v0",
        "status": "shipped",
        "title": "Closed-loop decisioning on sample warehouse",
        "items": [
            "Weekly brief + qCAC (quality-adjusted CAC) alongside standard CAC",
            "Funnel: visits -> prompt_starts -> signups -> activated -> paid",
            "Forecast Free->Paid using measured cohort rates (short + long loop)",
            "Constrained allocator with finance guardrails",
            "Geo holdout + A/B experiments with close recommendations",
            "Brand insight cards (test, don't generate)",
            "Append-only decision ledger",
            "Competitive lens: explain alerts, don't dashboard them",
            "Instagram UTM capture + message-match scoring",
            "DS model integration contract (ml_channel_scores)",
        ],
    },
    {
        "version": "v1",
        "status": "next",
        "title": "Connect live data; activation as north star",
        "items": [
            "Live warehouse feed (replace sample fixtures, same datasource interface)",
            "Per-user fct_user_events -> Time-to-First-App p50/p90 by channel",
            "Session-level UTM stitching (utm_content -> activation lookup)",
            "Server-side conversion API + postback lifecycle",
            "Slack alerts on CAC/qCAC/payback drift",
            "Themed paid LPs by utm_content (Coframe integration)",
        ],
    },
    {
        "version": "v1.5",
        "status": "planned",
        "title": "Measured LTV; expansion modeling; COGS-aware CAC",
        "items": [
            "Replace hardcoded CHANNEL_LTV_MULTIPLIER with measured paid_rate x ARPU",
            "Allocator switches to blended signal (activation + forecast paid + lagged paid)",
            "Expansion loop: Core->Pro + credit top-ups as separate events",
            "PQL-style activation gating in conversion denominator",
            "Contribution-margin CAC = revenue - inference - hosting (per Sacra AI-tax)",
            "Per-channel cohort LTV decay curves",
        ],
    },
    {
        "version": "v2",
        "status": "planned",
        "title": "Causal allocator + continuous competitive intelligence",
        "items": [
            "MMM to calibrate MTA + holdout incrementality",
            "CUPED variance reduction on experiments",
            "Auto-paused fatigued creative within Brand-set guardrails",
            "Auto-rebalance budget within guardrails (human-in-loop opt-out)",
            "Continuous competitor signal ingest (SimilarWeb, Semrush APIs)",
            "Threat index per channel (replaces hand-authored alert explainer)",
            "Cross-segment LTV transfer learning (consumer signups -> enterprise pipeline)",
        ],
    },
]


def build_roadmap() -> dict:
    return {
        "title": "Roadmap",
        "tagline": "v0 ships the loop. v1 connects. v1.5 measures. v2 acts.",
        "versions": ROADMAP,
    }
