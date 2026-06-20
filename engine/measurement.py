"""Measurement, alerting, geo decomposition."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import config
from engine.periods import wow_delta


def aggregate_week(perf_rows: list[dict], segment: str, week_start: str) -> dict:
    spend = new_conv = conv = value = 0.0
    for r in perf_rows:
        if r["segment"] != segment or r["week_start"] != week_start:
            continue
        spend += float(r["spend"])
        new_conv += float(r["new_user_conversions"])
        conv += float(r["conversions"])
        value += float(r.get("conversion_value") or 0)
    cac = spend / new_conv if new_conv else 0
    net_new_pct = new_conv / conv if conv else 0
    guard = config.FINANCE_GUARDRAILS[segment]
    ltv = (value / new_conv) if new_conv else 0
    ltv_cac = ltv / cac if cac else 0
    payback = cac / (ltv / 12) if ltv else 0
    return {
        "spend": spend,
        "conversions": conv,
        "new_user_conversions": new_conv,
        "net_new_pct": net_new_pct,
        "cac": cac,
        "ltv": ltv,
        "ltv_cac": ltv_cac,
        "payback_months": payback,
        "cac_ceiling": guard["cac_ceiling"],
        "payback_target": guard["payback_target_months"],
        "ltv_cac_target": guard["ltv_cac_target"],
    }


def geo_decomposition(perf_rows: list[dict], segment: str, week_start: str) -> list[dict]:
    by_geo: dict[str, dict] = defaultdict(lambda: {"spend": 0.0, "new_conv": 0.0})
    for r in perf_rows:
        if r["segment"] != segment or r["week_start"] != week_start:
            continue
        g = r["geo"]
        by_geo[g]["spend"] += float(r["spend"])
        by_geo[g]["new_conv"] += float(r["new_user_conversions"])
    rows = []
    for geo in config.GEOS:
        v = by_geo.get(geo, {"spend": 0, "new_conv": 0})
        cac = v["spend"] / v["new_conv"] if v["new_conv"] else 0
        arpu = config.GEO_ARPU_MULTIPLIER[geo]
        rows.append({
            "geo": geo,
            "spend": round(v["spend"]),
            "new_conversions": round(v["new_conv"], 1),
            "cac": round(cac, 2),
            "arpu_multiplier": arpu,
            "flag": "underwater" if geo == "LATAM" and cac > 40 and segment == "consumer" else "",
        })
    return rows


def channel_table(perf_rows: list[dict], segment: str, week: str, prior_week: str) -> list[dict]:
    def agg(ws):
        d = defaultdict(lambda: {"spend": 0.0, "new_conv": 0.0})
        for r in perf_rows:
            if r["segment"] != segment or r["week_start"] != ws:
                continue
            d[r["channel"]]["spend"] += float(r["spend"])
            d[r["channel"]]["new_conv"] += float(r["new_user_conversions"])
        return d

    cur, pri = agg(week), agg(prior_week)
    rows = []
    for ch in config.CHANNELS[segment]:
        c = cur.get(ch, {"spend": 0, "new_conv": 0})
        p = pri.get(ch, {"spend": 0, "new_conv": 0})
        cac = c["spend"] / c["new_conv"] if c["new_conv"] else 0
        pcac = p["spend"] / p["new_conv"] if p["new_conv"] else 0
        rows.append({
            "channel": ch,
            "label": config.CHANNEL_LABELS.get(ch, ch),
            "spend": round(c["spend"]),
            "new_conversions": round(c["new_conv"], 1),
            "cac": round(cac, 2),
            "cac_wow": wow_delta(cac, pcac),
            "spend_wow": wow_delta(c["spend"], p["spend"]),
        })
    return sorted(rows, key=lambda x: -x["spend"])


def generate_alerts(
    perf_rows: list[dict],
    segment: str,
    week: str,
    prior_week: str,
    creative_insights: list[dict],
    attribution: dict,
) -> list[dict]:
    alerts = []
    cur = aggregate_week(perf_rows, segment, week)
    pri = aggregate_week(perf_rows, segment, prior_week)

    cac_d = wow_delta(cur["cac"], pri["cac"])
    if cac_d["pct"] and cac_d["pct"] > 0.08:
        alerts.append({
            "severity": "high",
            "type": "cac_shift",
            "title": "CAC shifted up WoW",
            "message": f"CAC {cur['cac']:.0f} vs {pri['cac']:.0f} prior week (+{cac_d['pct']*100:.1f}%)",
        })

    if cur["payback_months"] > cur["payback_target"] * 1.15:
        alerts.append({
            "severity": "medium",
            "type": "payback_drift",
            "title": "Payback drifting above target",
            "message": f"Payback {cur['payback_months']:.1f}mo vs target {cur['payback_target']}mo",
        })

    if cur["net_new_pct"] < 0.55 and segment == "consumer":
        alerts.append({
            "severity": "medium",
            "type": "signal_quality",
            "title": "Weak net-new signal",
            "message": (
                f"Only {cur['net_new_pct']*100:.0f}% of conversions are net-new. "
                "Optimizer uses net-new (filtered), not raw conversions — audiences are NOT excluded."
            ),
        })

    geo = geo_decomposition(perf_rows, segment, week)
    latam = next((g for g in geo if g["geo"] == "LATAM"), None)
    if latam and latam.get("flag") == "underwater":
        alerts.append({
            "severity": "high",
            "type": "geo_drag",
            "title": "LATAM geo drag",
            "message": "LATAM shows cheap CPM but underwater CAC — aggregate looks fine, region is not.",
        })

    diag = attribution.get("retargeting_diagnostic", {})
    if diag.get("overcredit_estimate_pct", 0) > 30:
        alerts.append({
            "severity": "medium",
            "type": "attribution_divergence",
            "title": "Retargeting over-credited in last-touch",
            "message": diag.get("plain_english", ""),
        })

    for ins in creative_insights:
        if ins.get("fatigue") == "high":
            alerts.append({
                "severity": "medium",
                "type": "creative_fatigue",
                "title": f"Creative fatigue: {ins['name']}",
                "message": ins.get("insight_summary", ""),
            })

    return alerts
