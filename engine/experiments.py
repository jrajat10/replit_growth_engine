"""Experiment stats — A/B and geo holdout with plain-English recommendations."""

from __future__ import annotations

import math
from typing import Any


def _z_test_pooled(p1: float, n1: float, p2: float, n2: float) -> tuple[float, float]:
    if n1 < 1 or n2 < 1:
        return 0.0, 1.0
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    if p_pool <= 0 or p_pool >= 1:
        return 0.0, 1.0
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p2 - p1) / se
    # two-tailed p approx
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    lift = (p2 - p1) / p1 if p1 > 0 else 0
    return lift, p


def _latest_cumulative(results: list[dict], experiment_id: str) -> dict:
    rows = [r for r in results if r["experiment_id"] == experiment_id]
    if not rows:
        return {}
    rows.sort(key=lambda x: x["week_start"])
    r = rows[-1]
    cn, vn = float(r["control_n"]), float(r["variant_n"])
    cc, vc = float(r["control_conversions"]), float(r["variant_conversions"])
    return {
        "control_n": cn, "variant_n": vn,
        "control_rate": cc / cn if cn else 0,
        "variant_rate": vc / vn if vn else 0,
        "control_conversions": cc,
        "variant_conversions": vc,
        "weeks_of_data": len(rows),
    }


def evaluate_experiment(exp: dict, results: list[dict]) -> dict[str, Any]:
    cum = _latest_cumulative(results, exp["experiment_id"])
    if not cum:
        return {"experiment_id": exp["experiment_id"], "status": "no_data"}

    lift, p = _z_test_pooled(
        cum["control_rate"], cum["control_n"],
        cum["variant_rate"], cum["variant_n"],
    )
    weeks = cum["weeks_of_data"]

    if exp["type"] == "geo_holdout":
        # variant = held-out geo (less spend / no ads) — lower conv rate = spend was incremental
        incremental = cum["control_rate"] > cum["variant_rate"]
        causal_lift = (cum["control_rate"] - cum["variant_rate"]) / cum["variant_rate"] if cum["variant_rate"] else 0
        if weeks >= 4 and p < 0.05 and incremental:
            rec = "stop"
            rec_text = (
                f"Holdout shows treated geos convert {causal_lift*100:.0f}% better — "
                f"spend IS incremental. Keep running or expand."
            )
            learning = f"Geo holdout confirms {exp.get('channel', '')} drives real lift in treated regions."
        elif weeks >= 6 and p > 0.15 and not incremental:
            rec = "stop"
            rec_text = (
                "Held-out geo performs similarly — spend may NOT be incremental. "
                "Recommend cutting or reallocating."
            )
            learning = f"Geo holdout suggests {exp.get('channel', '')} spend in {exp.get('holdout_geo', '')} is non-incremental."
        else:
            rec = "keep_running"
            rec_text = f"Need more weeks for causal read ({weeks} so far). Don't reallocate on attribution alone."
            learning = None
    else:
        if p < 0.05 and lift > 0:
            rec = "ship"
            rec_text = f"Variant wins with {lift*100:.1f}% lift (p={p:.3f}). Ship winner."
            learning = f"{exp['name']}: variant beat control by {lift*100:.1f}%."
        elif weeks >= 8 and p > 0.20:
            rec = "stop"
            rec_text = "No significant lift after 8 weeks. Stop test; bank learning."
            learning = f"{exp['name']}: inconclusive — no meaningful lift detected."
        else:
            rec = "keep_running"
            rec_text = f"Not significant yet (p={p:.3f}). Keep running."
            learning = None

    return {
        "experiment_id": exp["experiment_id"],
        "name": exp["name"],
        "type": exp["type"],
        "segment": exp["segment"],
        "channel": exp.get("channel", ""),
        "status": exp["status"],
        "hypothesis": exp.get("hypothesis", ""),
        "holdout_geo": exp.get("holdout_geo", ""),
        "weeks_of_data": weeks,
        "control_rate": round(cum["control_rate"] * 100, 2),
        "variant_rate": round(cum["variant_rate"] * 100, 2),
        "lift_pct": round(lift * 100, 1),
        "p_value": round(p, 4),
        "recommendation": rec,
        "recommendation_text": rec_text,
        "learning": learning,
        "incrementality_first": exp["type"] == "geo_holdout",
        "plain_english": (
            "Geo holdout = turn off ads in one region, compare to similar region still running ads. "
            "If conversions drop where ads run, the spend caused those conversions — not just correlated."
            if exp["type"] == "geo_holdout"
            else "A/B test = show different creative to two groups, measure which converts better."
        ),
    }


def evaluate_all(experiments: list[dict], results: list[dict]) -> list[dict]:
    return [evaluate_experiment(e, results) for e in experiments]
