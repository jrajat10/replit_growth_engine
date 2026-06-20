# Replit Growth Engine

Closed-loop paid acquisition + lifecycle decisioning console for Replit's growth org (AMER, weekly).

**Built for:** Product Lead, Growth Marketing onsite portfolio artifact.

## Run locally

```bash
cd replit_growth_engine
pip install -r requirements.txt
python main.py
```

Open http://127.0.0.1:5000 → **Enter cockpit**

## Deploy on Replit

1. Push to GitHub or drag-drop the `replit_growth_engine` folder
2. Replit auto-detects `main.py` via `.replit`
3. Run → public `.replit.app` URL

## Features (v0)

| # | Feature | Tab |
|---|---------|-----|
| 1 | **Weekly Decision Memo** — narrative-first Growth Council Brief | Weekly Brief |
| 2 | **Monday Allocation Review** — single killer workflow | Monday Allocation |
| 3 | **Simple constrained allocation** — net-new efficiency × LTV, within guardrails | Monday Allocation |
| 4 | **Incrementality-first** — geo holdout hero; attribution = diagnostic only | Experiments, Performance |
| 5 | **Decision ledger** — append-only log of recommendations + approvals | Weekly Brief |
| 6 | **Ask the growth engine** — NL Q&A with cited sources | Weekly Brief |
| 8 | **Segment toggle** — Consumer/PLG vs Enterprise surfaces | Header |
| 9 | **Insight Cards → Brand** — fatigue + handoff (no copy generation) | Insight Cards |
| 10 | **Lifecycle as LTV input** — multiplier in allocation, not separate dashboard | Monday Allocation |

## Architecture

```
config.py           spec in code
engine/datasource   warehouse connector (sample CSV → live SQL in v1)
engine/ingest       sync + build state
engine/allocation   constrained greedy optimizer
engine/lifecycle    LTV multipliers → allocation
engine/attribution  simple last-touch vs Markov diagnostic
engine/experiments  A/B + geo holdout
engine/creative     insight cards
engine/knowledge    decisions.jsonl ledger
engine/decision_memo  weekly brief
engine/nl_query     templated Q&A
app.py              Flask API
```

## Data

Sample warehouse fixtures in `data/sample/`. Regenerate:

```bash
python tools/generate_sample.py
```

Swap to live: edit `engine/datasource.py` only.

## Boundaries

- **Brand** owns creative → we test & send insight cards
- **Finance** owns envelope → math allocates within guardrails
- **DE** owns pipelines → we consume the contract
- App **recommends**; humans approve (logged to ledger)
