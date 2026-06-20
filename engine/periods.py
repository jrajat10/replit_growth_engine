"""Weekly calendar and WoW/QoQ helpers."""

from __future__ import annotations

from datetime import date, timedelta


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_label(ws: date) -> str:
    end = ws + timedelta(days=6)
    return f"Week of {ws.strftime('%b %d')}–{end.strftime('%b %d, %Y')}"


def wow_delta(current: float, prior: float) -> dict:
    if prior == 0:
        return {"abs": current, "pct": None, "direction": "flat"}
    pct = (current - prior) / prior
    direction = "up" if pct > 0.01 else ("down" if pct < -0.01 else "flat")
    return {"abs": current - prior, "pct": pct, "direction": direction}


def qoq_delta(current: float, quarter_ago: float) -> dict:
    return wow_delta(current, quarter_ago)


def format_delta(d: dict, invert_good: bool = False) -> str:
    if d["pct"] is None:
        return "—"
    sign = "+" if d["pct"] >= 0 else ""
    good = d["direction"] == "down" if invert_good else d["direction"] == "up"
    arrow = "▲" if d["pct"] > 0 else ("▼" if d["pct"] < 0 else "→")
    return f"{arrow} {sign}{d['pct']*100:.1f}%"
