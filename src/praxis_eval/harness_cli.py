from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from praxis_eval.harness import run


def main() -> int:
    ap = argparse.ArgumentParser(description="Praxis eval harness (writes evals/out/latest.json).")
    ap.add_argument("--case", default=None)
    args = ap.parse_args()

    out_dir = Path("praxis_evals") / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = run(args.case)

    latest_path = out_dir / "latest.json"
    ts_path = out_dir / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

    latest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ts_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote: {latest_path}")
    print(f"Wrote: {ts_path}")
    return 0
