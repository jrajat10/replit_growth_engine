"""Entry point — sync data on boot, serve Flask."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app import app
from engine import ingest, knowledge
from tools.generate_sample import main as gen_sample

SAMPLE = Path(__file__).parent / "data" / "sample" / "fct_paid_performance.csv"


def bootstrap():
    if not SAMPLE.exists():
        print("Generating sample warehouse data...")
        gen_sample()
    ingest.sync_from_source()
    if not knowledge.read_all(1):
        knowledge.append({
            "type": "system",
            "message": "Growth engine initialized on sample warehouse data.",
            "human_action": "info",
        })


if __name__ == "__main__":
    bootstrap()
    port = int(os.environ.get("PORT", 5000))
    # Replit sets PORT; disable debug reload in published deployments
    debug = os.environ.get("REPLIT_DEPLOYMENT") != "1"
    print(f"Replit Growth Engine -> http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
