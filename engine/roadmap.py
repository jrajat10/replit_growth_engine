"""Roadmap surface — v0 / v1 / v1.5 / v2 shipped to landing + cockpit."""

ROADMAP = [
    {
        "version": "v0",
        "status": "shipped",
        "title": "Closed-loop decisioning on sample warehouse",
        "items": [
            "Weekly decision brief with CAC and qCAC (quality-adjusted CAC)",
            "Funnel: visits -> prompt_starts -> signups -> activated -> paid",
            "Free->Paid forecast from measured cohort rates (short + long loop)",
            "Constrained allocator: symmetric +/- weekly-shift band, CAC ceiling, "
            "diminishing-returns adjustment, ramp-limited reserve",
            "Incrementality-discounted scoring: geo-holdout evidence pulls budget "
            "out of non-incremental channels",
            "Pacing & quarterly targets: ARR -> channel signup waterfall on a seasonal curve",
            "Closed-loop: pacing miss -> guardrail-bounded corrective allocation, "
            "staged for approval",
            "Experiments: geo holdout + A/B with scale / ship / cut / keep-running calls",
            "Brand insight cards (engine tests; Brand owns copy)",
            "Append-only decision ledger",
            "Competitive lens: explains alerts with confidence + source",
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
            "MMM + holdout calibration of the incrementality discount v0 applies heuristically",
            "Measured marginal-ROAS / saturation curves replace the v0 diminishing-returns proxy",
            "CUPED variance reduction on experiments",
            "Auto-paused fatigued creative within Brand-set guardrails",
            "Auto-rebalance within guardrails (upgrades v0's staged-for-approval shift)",
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
