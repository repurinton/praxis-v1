from __future__ import annotations

import dataclasses
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _git_head_sha() -> Optional[str]:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:
        return None


def _safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _parse_bracket_list(s: str) -> list[str]:
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        parts = [p.strip().strip('"').strip("'") for p in inner.split(",")]
        return [p for p in parts if p]
    return [s.strip().strip('"').strip("'")]


def _parse_case(case_path: Optional[str]) -> Dict[str, Any]:
    if not case_path:
        return {"name": "default"}

    p = Path(case_path)
    case: Dict[str, Any] = {"name": p.stem, "path": str(p)}
    if not p.exists():
        case["parse_error"] = f"Case file not found: {p}"
        return case

    text = p.read_text(encoding="utf-8", errors="replace")

    if p.suffix.lower() == ".json":
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                obj.setdefault("name", p.stem)
                obj.setdefault("path", str(p))
                return obj
            return {"name": p.stem, "path": str(p), "parse_error": "JSON root was not an object"}
        except Exception as e:
            return {"name": p.stem, "path": str(p), "parse_error": f"JSON parse failed: {e}"}

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith(("  ", "\t", "-")):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = k.strip()
        val = v.strip()
        if not key:
            continue

        if key == "name":
            case["name"] = val.strip('"').strip("'")
            continue

        if key in ("evidence_coverage_min", "evidence_coverage_max"):
            fv = _safe_float(val)
            if fv is not None:
                case[key] = fv
            continue

        if key in ("verification_status_in", "release_decision_in"):
            case[key] = _parse_bracket_list(val)
            continue

    return case


def _coerce_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return dict(obj.__dict__)
        except Exception:
            pass
    return {"repr": repr(obj)}


def _norm_token(x: Any) -> Optional[str]:
    if x is None:
        return None
    if hasattr(x, "value"):
        try:
            return str(getattr(x, "value"))
        except Exception:
            pass
    try:
        return str(x)
    except Exception:
        return None


def _extract_coverage(verification: Any) -> Optional[float]:
    if isinstance(verification, dict):
        for k in ("evidence_coverage", "coverage"):
            if k in verification and isinstance(verification[k], (int, float)):
                return float(verification[k])

    for attr in ("evidence_coverage", "coverage"):
        if hasattr(verification, attr):
            v = getattr(verification, attr)
            if isinstance(v, (int, float)):
                return float(v)

    summary = None
    if isinstance(verification, dict):
        summary = verification.get("summary")
    elif hasattr(verification, "summary"):
        summary = getattr(verification, "summary")

    if isinstance(summary, str):
        m = re.search(r"evidence_coverage\s*=\s*([0-9]*\.?[0-9]+)", summary)
        if m:
            return _safe_float(m.group(1))
    return None


def _extract_status_and_checks(verification: Any) -> Tuple[Optional[Any], Any, Optional[str]]:
    if isinstance(verification, dict):
        status = verification.get("status") or verification.get("verification_status")
        checks = verification.get("checks")
        summary = verification.get("summary")
        return status, checks, summary

    status = getattr(verification, "status", None) or getattr(verification, "verification_status", None)
    checks = getattr(verification, "checks", None)
    summary = getattr(verification, "summary", None)
    return status, checks, summary


def _extract_release(release_obj: Any) -> Tuple[Optional[Any], Optional[str]]:
    if isinstance(release_obj, dict):
        return release_obj.get("decision"), release_obj.get("reason")

    decision = getattr(release_obj, "decision", None) or getattr(release_obj, "release_decision", None)
    reason = getattr(release_obj, "reason", None)
    return decision, reason


def run(case_path: Optional[str]) -> Dict[str, Any]:
    case = _parse_case(case_path)

    from praxis_core.generator_stub import generate_sample_claims
    from praxis_core.verification import verify_evidence_presence
    from praxis_core.release import decide_release

    claims = generate_sample_claims()
    verification = verify_evidence_presence(claims)
    release_obj = decide_release(verification)

    status, checks, summary = _extract_status_and_checks(
        _coerce_dict(verification) if not isinstance(verification, dict) else verification
    )
    if status is None:
        status, checks, summary = _extract_status_and_checks(verification)

    coverage = _extract_coverage(verification)
    decision, reason = _extract_release(release_obj)

    status_s = _norm_token(status)
    decision_s = _norm_token(decision)

    result: Dict[str, Any] = {
        "case": case,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head_sha(),
        "env": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        },
        "outputs": {
            "verification_status": status_s,
            "evidence_coverage": coverage,
            "summary": summary,
            "checks": checks,
            "release_decision": decision_s,
            "release_reason": reason,
        },
    }

    expectations: Dict[str, Any] = {}
    verdicts: Dict[str, Any] = {}

    if "evidence_coverage_min" in case:
        expectations["evidence_coverage_min"] = case["evidence_coverage_min"]
        verdicts["evidence_coverage_min_ok"] = (coverage is not None and coverage >= float(case["evidence_coverage_min"]))

    if "evidence_coverage_max" in case:
        expectations["evidence_coverage_max"] = case["evidence_coverage_max"]
        verdicts["evidence_coverage_max_ok"] = (coverage is not None and coverage <= float(case["evidence_coverage_max"]))

    if "verification_status_in" in case:
        allowed = {str(x).strip() for x in case["verification_status_in"]}
        expectations["verification_status_in"] = sorted(allowed)
        verdicts["verification_status_ok"] = (status_s is not None and status_s in allowed)

    if "release_decision_in" in case:
        allowed = {str(x).strip() for x in case["release_decision_in"]}
        expectations["release_decision_in"] = sorted(allowed)
        verdicts["release_decision_ok"] = (decision_s is not None and decision_s in allowed)

    if expectations:
        result["expectations"] = expectations
        result["verdicts"] = verdicts
        result["pass"] = bool(verdicts) and all(bool(v) for v in verdicts.values())
    else:
        result["pass"] = None

    return result
