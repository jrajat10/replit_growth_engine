# Deploy to Replit (for your onsite demo)

Follow these steps to publish a public URL you can share with interviewers.

---

## Option A — Import from GitHub (recommended)

### 1. Push the app to GitHub

From your machine:

```bash
cd replit_growth_engine
git init
git add .
git commit -m "Replit growth engine v0"
git remote add origin https://github.com/YOUR_USERNAME/replit-growth-engine.git
git push -u origin main
```

### 2. Create a new Repl

1. Go to [https://replit.com](https://replit.com) and sign in
2. Click **Create Repl**
3. Choose **Import from GitHub**
4. Select your `replit-growth-engine` repo
5. Replit detects Python and uses `main.py` automatically

### 3. Run in the workspace (preview)

1. Click the green **Run** button
2. Wait for: `Replit Growth Engine -> http://0.0.0.0:...`
3. Open the **Webview** panel (browser icon in Replit)
4. You should see the landing page → click **Enter cockpit**

### 4. Publish a public URL (what interviewers will open)

1. In the left sidebar, open **Deployments** (or **Publishing**)
2. Choose **Autoscale Deployment** (best for a Flask web app)
3. Click **Deploy**
4. Replit gives you a URL like:
   ```
   https://replit-growth-engine.YOUR_USERNAME.repl.co
   ```
5. Share that URL in your pre-read email / onsite materials

> **Tip:** Run a deploy 24 hours before the onsite and click through every tab once to confirm it loads.

---

## Option B — Upload folder directly (no GitHub)

1. Go to [https://replit.com](https://replit.com) → **Create Repl**
2. Choose **Python** template
3. Drag the entire `replit_growth_engine` folder into the Replit file tree
4. Ensure `main.py` is at the root
5. Click **Run** → then **Deploy** as above

---

## What Replit runs

| File | Purpose |
|------|---------|
| `main.py` | Boots app, reads `PORT` from Replit, serves Flask |
| `.replit` | Tells Replit to run `python main.py` and use Autoscale |
| `requirements.txt` | Installs `flask` |

On first run, `main.py` auto-generates sample data if `data/sample/` is empty.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Application failed to respond" | Check **Deployments** logs; ensure `main.py` binds to `0.0.0.0` and `PORT` |
| Blank page | Open `/cockpit` directly; check Run console for errors |
| Data missing | Click **Re-sync from source** on Data tab, or re-run Repl |
| Slow cold start | Normal on Autoscale free tier; first load may take 10–20s |

---

## What to tell interviewers

> "This is a v0 growth decisioning console built on Replit. It reads weekly conversion data from our warehouse contract (sample data today). The Data Science team publishes channel efficiency scores to `ml_channel_scores` — the allocator uses those when available and falls back to heuristics otherwise. I own the closed loop: measure → attribute → recommend → learn. Finance sets the envelope; the math decides where; humans approve."

---

## Pre-onsite checklist

- [ ] Public deploy URL works on phone (not just laptop)
- [ ] Weekly Brief loads with 3 bullets
- [ ] Segment toggle Consumer ↔ Enterprise works
- [ ] "Approve allocation" logs to decision ledger
- [ ] Ask box: try "Why LATAM TikTok?"
- [ ] Data tab shows DS model version (`channel_efficiency_v2.1`)
