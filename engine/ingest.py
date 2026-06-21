"""Ingest warehouse data and build analytics state."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from engine import datasource
from engine.allocation import allocate
from engine.attribution import analyze as attribution_analyze
from engine.creative import build_insight_cards
from engine.experiments import evaluate_all
from engine.lifecycle import compute_channel_ltv_multipliers
from engine.measurement import (
    aggregate_week,
    channel_table,
    generate_alerts,
    geo_decomposition,
)
from engine.periods import format_delta, week_label, wow_delta
from engine import knowledge
from engine.models import apply_to_allocation_scores, load_channel_scores, MODEL_CONTRACT
from engine.campaigns import build_campaign_intelligence
from engine.funnel import (
    funnel_overview, channel_funnel_table, forecast_free_to_paid,
    time_to_first_app_distribution, ACTIVATION_DEFINITION, QCAC_DEFINITION,
)
from engine.competition import attach_explanations, landscape_snapshot
from engine.roadmap import build_roadmap


class GrowthState:
    def __init__(self):
        self.perf: list[dict] = []
        self.paths: list[dict] = []
        self.experiments: list[dict] = []
        self.exp_results: list[dict] = []
        self.creatives: list[dict] = []
        self.creative_perf: list[dict] = []
        self.funnel: list[dict] = []
        self.competitors: list[dict] = []
        self.competitor_signals: list[dict] = []
        self.weeks: list[str] = []

    def sync(self):
        self.perf = datasource.load_paid_performance()
        self.paths = datasource.load_conversion_paths()
        self.experiments = datasource.load_experiments()
        self.exp_results = datasource.load_experiment_results()
        self.creatives = datasource.load_creatives()
        self.creative_perf = datasource.load_creative_performance()
        self.funnel = datasource.load_funnel_events()
        self.competitors = datasource.load_competitors()
        self.competitor_signals = datasource.load_competitor_signals()
        self.weeks = sorted({r["week_start"] for r in self.perf})

    def build(self, segment: str = "consumer") -> dict[str, Any]:
        if not self.weeks:
            self.sync()
        if not self.weeks:
            return {"error": "No data"}

        week = self.weeks[-1]
        prior = self.weeks[-2] if len(self.weeks) > 1 else week
        qago = self.weeks[-13] if len(self.weeks) >= 13 else self.weeks[0]

        cur = aggregate_week(self.perf, segment, week)
        pri = aggregate_week(self.perf, segment, prior)
        qag = aggregate_week(self.perf, segment, qago)

        ltv_mult = compute_channel_ltv_multipliers(self.perf, segment)
        prior_alloc = {
            ch: sum(float(r["spend"]) for r in self.perf
                    if r["segment"] == segment and r["channel"] == ch and r["week_start"] == prior)
            for ch in __import__("config").CHANNELS[segment]
        }
        model_output = load_channel_scores(week, segment)
        # Build heuristic scores for blend / fallback
        heuristic_scores = {}
        for ch in __import__("config").CHANNELS[segment]:
            m_spend = sum(float(r["spend"]) for r in self.perf
                          if r["segment"] == segment and r["channel"] == ch and r["week_start"] == week)
            m_new = sum(float(r["new_user_conversions"]) for r in self.perf
                        if r["segment"] == segment and r["channel"] == ch and r["week_start"] == week)
            eff = m_new / m_spend if m_spend else 0
            ltv = ltv_mult.get(ch, {}).get("ltv_multiplier", 1.0)
            heuristic_scores[ch] = eff * ltv
        final_scores, score_explanations = apply_to_allocation_scores(heuristic_scores, model_output)
        alloc = allocate(
            self.perf, segment, week, ltv_mult, prior_alloc,
            model_scores=final_scores if model_output.get("available") else None,
            score_explanations=score_explanations,
        )

        attr = attribution_analyze(self.paths, segment if segment == "consumer" else "consumer")
        cards = build_insight_cards(self.creatives, self.creative_perf, segment, week)
        exps = evaluate_all(self.experiments, self.exp_results)
        seg_exps = [e for e in exps if e.get("segment") == segment]

        alerts = generate_alerts(self.perf, segment, week, prior, cards, attr)
        alerts = attach_explanations(alerts, self.competitors, self.competitor_signals, week)

        funnel = funnel_overview(self.funnel, self.perf, segment, week)
        funnel_channels = channel_funnel_table(self.funnel, self.perf, segment, week)
        funnel_forecast = forecast_free_to_paid(self.funnel, segment, week, self.weeks)

        kpis = {
            "spend": {"value": cur["spend"], "wow": wow_delta(cur["spend"], pri["spend"]),
                      "qoq": wow_delta(cur["spend"], qag["spend"]), "fmt_wow": format_delta(wow_delta(cur["spend"], pri["spend"])),
                      "invert": False},
            "new_conversions": {"value": cur["new_user_conversions"], "wow": wow_delta(cur["new_user_conversions"], pri["new_user_conversions"]),
                                "fmt_wow": format_delta(wow_delta(cur["new_user_conversions"], pri["new_user_conversions"]))},
            "cac": {"value": cur["cac"], "wow": wow_delta(cur["cac"], pri["cac"]),
                    "fmt_wow": format_delta(wow_delta(cur["cac"], pri["cac"]), invert_good=True),
                    "target": cur["cac_ceiling"]},
            "qcac": {"value": funnel["qcac"], "definition": QCAC_DEFINITION,
                     "ratio_to_cac": funnel["qcac_to_cac_ratio"]},
            "activation_rate": {"value": funnel["activation_rate"],
                                "definition": ACTIVATION_DEFINITION},
            "ltv_cac": {"value": cur["ltv_cac"], "wow": wow_delta(cur["ltv_cac"], pri["ltv_cac"]),
                        "fmt_wow": format_delta(wow_delta(cur["ltv_cac"], pri["ltv_cac"])),
                        "target": cur["ltv_cac_target"]},
            "payback_months": {"value": cur["payback_months"], "wow": wow_delta(cur["payback_months"], pri["payback_months"]),
                               "fmt_wow": format_delta(wow_delta(cur["payback_months"], pri["payback_months"]), invert_good=True),
                               "target": cur["payback_target"]},
            "net_new_pct": {"value": cur["net_new_pct"], "wow": wow_delta(cur["net_new_pct"], pri["net_new_pct"]),
                            "fmt_wow": format_delta(wow_delta(cur["net_new_pct"], pri["net_new_pct"]))},
        }

        return {
            "segment": segment,
            "week_start": week,
            "week_label": week_label(date.fromisoformat(week)),
            "prior_week": prior,
            "kpis": kpis,
            "channels": channel_table(self.perf, segment, week, prior),
            "geo": geo_decomposition(self.perf, segment, week),
            "allocation": alloc,
            "ltv_multipliers": ltv_mult,
            "attribution": attr,
            "experiments": seg_exps,
            "creative_cards": cards,
            "alerts": alerts,
            "ledger": knowledge.read_all(12),
            "data_source": datasource.connection_status(),
            "model": {
                "available": model_output.get("available", False),
                "version": model_output.get("model_version", "heuristic"),
                "source": model_output.get("source", "none"),
                "scored_at": model_output.get("scored_at", ""),
                "contract": MODEL_CONTRACT,
            },
            "paid_campaigns": build_campaign_intelligence(self.perf, segment),
            "funnel": funnel,
            "funnel_channels": funnel_channels,
            "funnel_forecast": funnel_forecast,
            "time_to_first_app": time_to_first_app_distribution(self.funnel, segment, week),
            "competition": landscape_snapshot(self.competitors, self.competitor_signals),
            "roadmap": build_roadmap(),
        }


_state = GrowthState()


def get_state(segment: str = "consumer") -> dict:
    return _state.build(segment)


def sync_from_source():
    _state.sync()
    return _state.weeks


def get_trends(segment: str = "consumer") -> dict:
    if not _state.weeks:
        _state.sync()
    weeks = _state.weeks[-8:]
    result = []
    for w in weeks:
        agg = aggregate_week(_state.perf, segment, w)
        result.append({
            "week": w,
            "label": week_label(date.fromisoformat(w)),
            "spend": round(agg["spend"]),
            "cac": round(agg["cac"]),
            "new_conversions": round(agg["new_user_conversions"]),
            "ltv_cac": round(agg["ltv_cac"], 2),
        })
    return {"segment": segment, "weeks": result}
