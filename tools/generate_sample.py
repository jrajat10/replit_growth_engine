"""One-off generator for labeled sample warehouse fixtures."""

from __future__ import annotations

import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config

OUT = Path(__file__).resolve().parent.parent / "data" / "sample"
random.seed(42)

START = date(2026, 3, 17)  # Monday
WEEKS = 14


def weeks_list():
    return [START + timedelta(weeks=i) for i in range(WEEKS)]


def channel_params(segment: str, channel: str) -> dict:
    base = {
        ("consumer", "google_brand"): {"spend": 22000, "cpc": 1.2, "cvr": 0.09, "new_ratio": 0.35},
        ("consumer", "google_nonbrand"): {"spend": 55000, "cpc": 2.8, "cvr": 0.05, "new_ratio": 0.88},
        ("consumer", "meta_prospect"): {"spend": 95000, "cpc": 1.1, "cvr": 0.028, "new_ratio": 0.92},
        ("consumer", "meta_retarget"): {"spend": 42000, "cpc": 0.7, "cvr": 0.06, "new_ratio": 0.25},
        ("consumer", "tiktok_creator"): {"spend": 78000, "cpc": 0.55, "cvr": 0.018, "new_ratio": 0.95},
        ("consumer", "youtube"): {"spend": 28000, "cpc": 2.1, "cvr": 0.022, "new_ratio": 0.80},
        ("consumer", "reddit_test"): {"spend": 8000, "cpc": 1.8, "cvr": 0.015, "new_ratio": 0.85},
        ("enterprise", "google_brand"): {"spend": 12000, "cpc": 3.5, "cvr": 0.04, "new_ratio": 0.40},
        ("enterprise", "google_nonbrand"): {"spend": 28000, "cpc": 6.2, "cvr": 0.018, "new_ratio": 0.90},
        ("enterprise", "linkedin_abm"): {"spend": 72000, "cpc": 8.5, "cvr": 0.012, "new_ratio": 0.93},
        ("enterprise", "linkedin_retarget"): {"spend": 22000, "cpc": 5.0, "cvr": 0.025, "new_ratio": 0.30},
        ("enterprise", "meta_prospect"): {"spend": 18000, "cpc": 2.2, "cvr": 0.008, "new_ratio": 0.88},
        ("enterprise", "youtube"): {"spend": 15000, "cpc": 4.0, "cvr": 0.01, "new_ratio": 0.75},
    }
    return base[(segment, channel)]


def geo_mix(channel: str) -> dict[str, float]:
    if channel == "tiktok_creator":
        return {"US_W": 0.22, "US_E": 0.28, "US_C": 0.18, "CA": 0.07, "LATAM": 0.25}
    if channel in ("linkedin_abm", "linkedin_retarget"):
        return {"US_W": 0.35, "US_E": 0.35, "US_C": 0.15, "CA": 0.12, "LATAM": 0.03}
    return {"US_W": 0.30, "US_E": 0.30, "US_C": 0.20, "CA": 0.12, "LATAM": 0.08}


def generate_paid_performance():
    rows = []
    last_wi = WEEKS - 1
    for wi, ws in enumerate(weeks_list()):
        drift = 1 + wi * 0.01
        fatigue_tiktok = max(0.75, 1 - wi * 0.02) if wi > 4 else 1.0
        # Last week: competitive pressure event — Meta CPM up, CVR squeezed.
        # Used to demonstrate the competitor-explained-alert beat end-to-end.
        meta_cpc_inflator = 1.13 if wi == last_wi else 1.0
        meta_cvr_squeeze = 0.86 if wi == last_wi else 1.0
        for segment in config.SEGMENTS:
            for channel in config.CHANNELS[segment]:
                p = channel_params(segment, channel)
                mix = geo_mix(channel)
                for geo, share in mix.items():
                    spend = p["spend"] * share * drift * random.uniform(0.92, 1.08)
                    if channel == "tiktok_creator":
                        spend *= fatigue_tiktok
                    cpc = p["cpc"]
                    if channel.startswith("meta_"):
                        cpc *= meta_cpc_inflator
                    clicks = max(1, int(spend / cpc * random.uniform(0.95, 1.05)))
                    cvr = p["cvr"] * random.uniform(0.9, 1.1)
                    if channel.startswith("meta_"):
                        cvr *= meta_cvr_squeeze
                    if geo == "LATAM":
                        cvr *= 0.85
                    conversions = clicks * cvr
                    new_conv = conversions * p["new_ratio"]
                    ret_conv = conversions - new_conv
                    arpu = config.GEO_ARPU_MULTIPLIER[geo]
                    value = new_conv * (120 if segment == "consumer" else 2800) * arpu
                    rows.append({
                        "week_start": ws.isoformat(),
                        "segment": segment,
                        "channel": channel,
                        "geo": geo,
                        "spend": f"{spend:.2f}",
                        "impressions": int(clicks * random.randint(8, 15)),
                        "clicks": clicks,
                        "conversions": f"{conversions:.2f}",
                        "new_user_conversions": f"{new_conv:.2f}",
                        "returning_user_conversions": f"{ret_conv:.2f}",
                        "conversion_value": f"{value:.2f}",
                    })
    return rows


def generate_conversion_paths():
    rows = []
    channels = ["google_nonbrand", "meta_prospect", "tiktok_creator", "youtube", "meta_retarget"]
    for i in range(400):
        converted = random.random() < 0.22
        path_len = random.randint(1, 4)
        path = random.sample(channels, k=min(path_len, len(channels)))
        if converted and "meta_retarget" not in path and random.random() < 0.4:
            path.append("meta_retarget")
        rows.append({
            "path_id": f"p{i:04d}",
            "segment": "consumer",
            "touch_sequence": ">".join(path),
            "converted": "1" if converted else "0",
            "conversion_value": f"{random.uniform(80, 200):.2f}" if converted else "0",
        })
    return rows


def generate_experiments():
    return [
        {
            "experiment_id": "exp_geo_holdout_latam",
            "name": "LATAM TikTok incrementality holdout",
            "type": "geo_holdout",
            "segment": "consumer",
            "channel": "tiktok_creator",
            "status": "running",
            "start_week": (START + timedelta(weeks=8)).isoformat(),
            "holdout_geo": "LATAM",
            "hypothesis": "LATAM TikTok spend is not incremental at current CAC",
        },
        {
            "experiment_id": "exp_ab_creative_speed",
            "name": "Speed demo vs income-claim creative",
            "type": "ab_test",
            "segment": "consumer",
            "channel": "tiktok_creator",
            "status": "running",
            "start_week": (START + timedelta(weeks=10)).isoformat(),
            "holdout_geo": "",
            "hypothesis": "Speed-demo hook beats income-claim on net-new CAC",
        },
        {
            "experiment_id": "exp_ab_enterprise_form",
            "name": "Embedded form vs CTA button (enterprise LP)",
            "type": "ab_test",
            "segment": "enterprise",
            "channel": "linkedin_abm",
            "status": "completed",
            "start_week": (START + timedelta(weeks=4)).isoformat(),
            "holdout_geo": "",
            "hypothesis": "Embedded form reduces friction on demo requests",
        },
    ]


def generate_experiment_results(experiments):
    rows = []
    for exp in experiments:
        eid = exp["experiment_id"]
        start = date.fromisoformat(exp["start_week"])
        for wi in range(WEEKS):
            ws = weeks_list()[wi]
            if ws < start:
                continue
            weeks_in = (ws - start).days // 7 + 1
            if exp["type"] == "geo_holdout":
                ctrl_n = 8000 + wi * 500
                var_n = 7500 + wi * 480
                ctrl_conv = ctrl_n * 0.014
                var_conv = var_n * 0.0135 * (1 - 0.12 * min(weeks_in, 4) / 4)
            elif eid == "exp_ab_creative_speed":
                ctrl_n = 12000 + wi * 800
                var_n = 11800 + wi * 820
                ctrl_conv = ctrl_n * 0.019
                var_conv = var_n * 0.024
            else:
                ctrl_n = 4000 + wi * 200
                var_n = 4100 + wi * 210
                ctrl_conv = ctrl_n * 0.028
                var_conv = var_n * 0.041
            rows.append({
                "experiment_id": eid,
                "week_start": ws.isoformat(),
                "control_n": f"{ctrl_n:.0f}",
                "variant_n": f"{var_n:.0f}",
                "control_conversions": f"{ctrl_conv:.2f}",
                "variant_conversions": f"{var_conv:.2f}",
            })
    return rows


def generate_creatives():
    return [
        {"creative_id": "cr_tk_ugc_07", "name": "TikTok UGC #7 — income claim", "channel": "tiktok_creator",
         "segment": "consumer", "brand_directive": "creator_ugc", "status": "active"},
        {"creative_id": "cr_tk_speed_02", "name": "TikTok Speed Demo v2", "channel": "tiktok_creator",
         "segment": "consumer", "brand_directive": "speed_demo", "status": "active"},
        {"creative_id": "cr_meta_car_04", "name": "Meta Carousel Agent 4", "channel": "meta_prospect",
         "segment": "consumer", "brand_directive": "no_code_promise", "status": "active"},
        {"creative_id": "cr_li_ent_01", "name": "LinkedIn Enterprise Proof", "channel": "linkedin_abm",
         "segment": "enterprise", "brand_directive": "enterprise_proof", "status": "active"},
        {"creative_id": "cr_g_nb_03", "name": "Google Non-Brand Vibe Coding", "channel": "google_nonbrand",
         "segment": "consumer", "brand_directive": "no_code_promise", "status": "active"},
    ]


def generate_creative_performance(creatives):
    rows = []
    for cr in creatives:
        base_imp = 120000 if cr["channel"] == "tiktok_creator" else 80000
        fatigue = 1.0
        for wi, ws in enumerate(weeks_list()):
            if cr["creative_id"] == "cr_tk_ugc_07" and wi > 6:
                fatigue = max(0.55, 1 - (wi - 6) * 0.06)
            imp = int(base_imp * fatigue * random.uniform(0.9, 1.1))
            ctr = 0.022 * fatigue * random.uniform(0.9, 1.1)
            clicks = max(1, int(imp * ctr))
            cvr = 0.02 * random.uniform(0.85, 1.15)
            conv = clicks * cvr
            rows.append({
                "creative_id": cr["creative_id"],
                "week_start": ws.isoformat(),
                "impressions": imp,
                "clicks": clicks,
                "conversions": f"{conv:.2f}",
            })
    return rows


def write_csv(name: str, rows: list[dict], fieldnames: list[str]):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def generate_funnel_events(perf_rows):
    """
    fct_funnel_events: weekly x segment x channel x geo, multi-stage funnel.

    Stages reflect Replit's actual 2026 funnel:
      visits -> prompt_starts (landing intent)
              -> signups (forced auth after prompt)
              -> activated_first_app (first published deploy within 7d)
              -> paid_conversions (free -> Core/Pro)

    Conversion rates are channel-aware: TikTok drives volume but weak
    activation; LinkedIn ABM small volume, high activation -> paid.
    """
    activation_quality = {
        "google_brand": 0.62,
        "google_nonbrand": 0.55,
        "meta_prospect": 0.42,
        "meta_retarget": 0.50,
        "tiktok_creator": 0.32,
        "youtube": 0.48,
        "reddit_test": 0.46,
        "linkedin_abm": 0.71,
        "linkedin_retarget": 0.58,
    }
    paid_rate = {
        "google_brand": 0.085,
        "google_nonbrand": 0.062,
        "meta_prospect": 0.035,
        "meta_retarget": 0.052,
        "tiktok_creator": 0.022,
        "youtube": 0.040,
        "reddit_test": 0.038,
        "linkedin_abm": 0.140,
        "linkedin_retarget": 0.095,
    }
    rows = []
    for r in perf_rows:
        ch = r["channel"]
        seg = r["segment"]
        signups = float(r["new_user_conversions"])
        # visits ~ clicks * landing reach factor
        visits = int(float(r["clicks"]) * random.uniform(0.92, 1.05))
        # prompt_starts: users who type into the hero before auth wall
        prompt_starts = int(visits * random.uniform(0.18, 0.28))
        # signups already counted as new_user_conversions
        act_rate = activation_quality.get(ch, 0.45) * random.uniform(0.92, 1.08)
        if r["geo"] == "LATAM":
            act_rate *= 0.78
        activated = signups * act_rate
        pr = paid_rate.get(ch, 0.04) * random.uniform(0.85, 1.15)
        if r["geo"] == "LATAM":
            pr *= 0.55  # low ARPU geo
        paid = activated * pr
        rows.append({
            "week_start": r["week_start"],
            "segment": seg,
            "channel": ch,
            "geo": r["geo"],
            "visits": visits,
            "prompt_starts": prompt_starts,
            "signups": f"{signups:.2f}",
            "activated_first_app": f"{activated:.2f}",
            "paid_conversions": f"{paid:.3f}",
        })
    return rows


def generate_competitors():
    return [
        {
            "competitor_id": "lovable",
            "name": "Lovable",
            "primary_threat_segment": "consumer",
            "headline_metric": "$500M ARR (May 2026)",
            "funding": "$330M Series B @ $6.6B (Dec 2025)",
            "users": "8M users, 100k+ projects/day",
            "positioning": "Visual-first vibe coding; Figma-style UX",
        },
        {
            "competitor_id": "bolt_new",
            "name": "Bolt.new (StackBlitz)",
            "primary_threat_segment": "consumer",
            "headline_metric": "~$40M ARR in 6 months",
            "funding": "Open-source distribution",
            "users": "Strong dev-community pull",
            "positioning": "Fast prototyping for technical users",
        },
        {
            "competitor_id": "v0_app",
            "name": "v0 (Vercel)",
            "primary_threat_segment": "consumer",
            "headline_metric": "Vercel distribution",
            "funding": "v0.dev rebrand -> v0.app (Jan 2026)",
            "users": "Front-end / UI quality narrative",
            "positioning": "UI / frontend quality leader",
        },
        {
            "competitor_id": "base44",
            "name": "Base44",
            "primary_threat_segment": "enterprise",
            "headline_metric": "Acquired (~$80M)",
            "funding": "Category consolidation play",
            "users": "Enterprise pivot",
            "positioning": "Enterprise vibe coding",
        },
    ]


def generate_competitor_signals():
    """
    fct_competitor_signals: hand-authored / manually captured signals.
    Each signal has a CONFIDENCE and SOURCE so the engine can label provenance.
    """
    latest = (START + timedelta(weeks=WEEKS - 1)).isoformat()
    return [
        {
            "signal_id": "cs_001",
            "week_start": latest,
            "competitor_id": "lovable",
            "channel": "google_nonbrand",
            "signal_type": "impression_share_change",
            "value": "+12pts",
            "confidence": "0.78",
            "source": "SimilarWeb (manual capture, 2026-06-19)",
            "interpretation": "Lovable expanded non-brand bids on vibe-coding keywords",
            "implication": "Replit CAC inflation likely market-driven, not funnel-driven",
        },
        {
            "signal_id": "cs_002",
            "week_start": latest,
            "competitor_id": "v0_app",
            "channel": "meta_prospect",
            "signal_type": "creative_volume_change",
            "value": "+18 active ads WoW",
            "confidence": "0.65",
            "source": "Meta Ad Library (manual capture, 2026-06-20)",
            "interpretation": "v0 ramping Meta prospecting alongside v0.dev->v0.app rebrand",
            "implication": "Watch IG/FB CPM uplift; defend Replit Meta prospecting spend",
        },
        {
            "signal_id": "cs_003",
            "week_start": latest,
            "competitor_id": "lovable",
            "channel": "tiktok_creator",
            "signal_type": "funding_signal",
            "value": "$330M Series B",
            "confidence": "0.95",
            "source": "TechCrunch / public filing",
            "interpretation": "Lovable has runway to outspend on creator partnerships",
            "implication": "Compete on creator quality, not creator volume",
        },
    ]


def generate_ml_channel_scores(perf_rows):
    """Simulate DS team weekly model output published to warehouse."""
    from datetime import datetime, timezone
    rows = []
    latest_week = max(r["week_start"] for r in perf_rows)
    scored_at = datetime.now(timezone.utc).isoformat()
    version = "channel_efficiency_v2.1"

    for segment in config.SEGMENTS:
        for channel in config.CHANNELS[segment]:
            spend = sum(float(r["spend"]) for r in perf_rows
                        if r["week_start"] == latest_week and r["segment"] == segment and r["channel"] == channel)
            new_c = sum(float(r["new_user_conversions"]) for r in perf_rows
                        if r["week_start"] == latest_week and r["segment"] == segment and r["channel"] == channel)
            per_dollar = new_c / spend if spend else 0
            # DS model adds smoothing + prior (slightly different from raw)
            predicted = per_dollar * random.uniform(0.92, 1.08)
            ltv = 120 if segment == "consumer" else 2800
            if channel == "tiktok_creator":
                predicted *= 0.82  # model correctly down-weights TikTok
            if channel == "google_nonbrand":
                predicted *= 1.12
            efficiency = predicted * (ltv / 100)
            rows.append({
                "week_start": latest_week,
                "segment": segment,
                "channel": channel,
                "predicted_net_new_per_dollar": f"{predicted:.6f}",
                "predicted_ltv": f"{ltv:.2f}",
                "efficiency_score": f"{efficiency:.6f}",
                "confidence": f"{random.uniform(0.72, 0.95):.2f}",
                "model_version": version,
                "scored_at": scored_at,
            })
    return rows


def main():
    perf = generate_paid_performance()
    exps = generate_experiments()
    creatives = generate_creatives()
    write_csv("fct_paid_performance.csv", perf,
              ["week_start", "segment", "channel", "geo", "spend", "impressions", "clicks",
               "conversions", "new_user_conversions", "returning_user_conversions", "conversion_value"])
    write_csv("fct_conversion_paths.csv", generate_conversion_paths(),
              ["path_id", "segment", "touch_sequence", "converted", "conversion_value"])
    write_csv("dim_experiments.csv", exps,
              ["experiment_id", "name", "type", "segment", "channel", "status", "start_week",
               "holdout_geo", "hypothesis"])
    write_csv("fct_experiment_results.csv", generate_experiment_results(exps),
              ["experiment_id", "week_start", "control_n", "variant_n",
               "control_conversions", "variant_conversions"])
    write_csv("dim_creative.csv", creatives,
              ["creative_id", "name", "channel", "segment", "brand_directive", "status"])
    write_csv("fct_creative_performance.csv", generate_creative_performance(creatives),
              ["creative_id", "week_start", "impressions", "clicks", "conversions"])
    write_csv("ml_channel_scores.csv", generate_ml_channel_scores(perf),
              ["week_start", "segment", "channel", "predicted_net_new_per_dollar",
               "predicted_ltv", "efficiency_score", "confidence", "model_version", "scored_at"])
    write_csv("fct_funnel_events.csv", generate_funnel_events(perf),
              ["week_start", "segment", "channel", "geo",
               "visits", "prompt_starts", "signups", "activated_first_app", "paid_conversions"])
    write_csv("dim_competitor.csv", generate_competitors(),
              ["competitor_id", "name", "primary_threat_segment", "headline_metric",
               "funding", "users", "positioning"])
    write_csv("fct_competitor_signals.csv", generate_competitor_signals(),
              ["signal_id", "week_start", "competitor_id", "channel", "signal_type",
               "value", "confidence", "source", "interpretation", "implication"])
    print(f"Generated sample data in {OUT}")


if __name__ == "__main__":
    main()
