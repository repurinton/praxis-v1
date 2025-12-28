from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional


def _git_rev_short() -> str:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        rev = (p.stdout or "").strip()
        return rev if rev else "unknown"
    except Exception:
        return "unknown"


def _jsonable(x: Any) -> Any:
    # Make best-effort conversion to JSON-serializable structures.
    if x is None:
        return None
    if is_dataclass(x):
        return {k: _jsonable(v) for k, v in asdict(x).items()}
    if isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, Path):
        return str(x)
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_jsonable(v) for v in x]
    # Common SDK objects / enums: try .value, else repr
    if hasattr(x, "value"):
        try:
            return _jsonable(getattr(x, "value"))
        except Exception:
            pass
    # Generic objects: try __dict__
    if hasattr(x, "__dict__"):
        try:
            return {k: _jsonable(v) for k, v in vars(x).items() if not k.startswith("_")}
        except Exception:
            pass
    return repr(x)


def _claim_snapshot(claim: Any) -> Dict[str, Any]:
    # Avoid tight coupling to Claim dataclass fields; snapshot what’s there.
    snap: Dict[str, Any] = {}
    for k in ("id", "claim_id", "text", "statement", "value", "metric", "unit", "company", "period"):
        if hasattr(claim, k):
            snap[k] = _jsonable(getattr(claim, k))
    # Evidence is commonly claim.evidence or claim.evidences
    ev = None
    for ek in ("evidence", "evidences", "sources"):
        if hasattr(claim, ek):
            ev = getattr(claim, ek)
            break
    if ev is not None:
        snap["evidence"] = _jsonable(ev)
        try:
            snap["evidence_count"] = len(ev)  # type: ignore[arg-type]
        except Exception:
            pass
    return snap


def build_run_artifact(
    *,
    run_source: str,
    dataset_root: Optional[str],
    min_attribution_coverage: float,
    planner_output: Optional[str],
    controller_output: Optional[str],
    claims: Any,
    verification_report: Any,
    release_outcome: Any,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ts = time.strftime("%Y%m%d_%H%M%S")
    rev = _git_rev_short()

    planner_txt = planner_output or ""
    controller_txt = controller_output or ""

    # Keep outputs (useful for research), but also include hashes/lengths implicitly via content.
    artifact: Dict[str, Any] = {
        "schema": "praxis.run_artifact.v1",
        "timestamp": ts,
        "git_rev": rev,
        "run_source": run_source,
        "inputs": {
            "dataset_root": dataset_root,
            "min_attribution_coverage": float(min_attribution_coverage),
        },
        "planner": {
            "enabled": bool(planner_output is not None),
            "output": planner_txt,
            "output_len": len(planner_txt),
        },
        "controller": {
            "enabled": bool(controller_output is not None),
            "output": controller_txt,
            "output_len": len(controller_txt),
        },
        "claims": {
            "count": (len(claims) if hasattr(claims, "__len__") else None),
            "items": [_claim_snapshot(c) for c in (claims or [])],
        },
        "verification": _jsonable(verification_report),
        "release": _jsonable(release_outcome),
    }

    if extra:
        artifact["extra"] = _jsonable(extra)

    return artifact


def write_run_artifact(
    artifact: Dict[str, Any],
    *,
    runs_dir: Optional[str] = None,
) -> Path:
    out_dir = Path(runs_dir or os.environ.get("PRAXIS_RUNS_DIR", "praxis_runs"))
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = artifact.get("timestamp") or time.strftime("%Y%m%d_%H%M%S")
    rev = artifact.get("git_rev", "unknown")
    path = out_dir / f"run_{ts}_{rev}.json"

    path.write_text(json.dumps(artifact, indent=2, sort_keys=False), encoding="utf-8")
    (out_dir / "latest.json").write_text(json.dumps(artifact, indent=2, sort_keys=False), encoding="utf-8")
    return path
