from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from evals.eval import Eval
from praxis_eval.harness import run as run_gate


class PraxisGateEval(Eval):
    def __init__(self, completion_fns, samples_jsonl: str, *args, **kwargs):
        super().__init__(completion_fns=completion_fns, samples_jsonl=samples_jsonl, *args, **kwargs)
        if not samples_jsonl:
            raise ValueError("samples_jsonl is required")
        self.samples_path = Path(samples_jsonl)

    def _iter_samples(self):
        with self.samples_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    yield line

    def _eval_one(self, sample: Any) -> Tuple[bool, float, Dict[str, Any]]:
        case_path: Optional[str] = None
        if isinstance(sample, dict):
            case_path = sample.get("case") or sample.get("case_path")
        elif isinstance(sample, str):
            try:
                obj = json.loads(sample)
                if isinstance(obj, dict):
                    case_path = obj.get("case") or obj.get("case_path")
            except Exception:
                case_path = None

        payload: Dict[str, Any] = run_gate(case_path)

        ok = payload.get("pass")
        ok_bool = bool(ok) if ok is not None else False

        cov = payload.get("outputs", {}).get("evidence_coverage", None)
        cov_val = float(cov) if isinstance(cov, (int, float)) else 0.0

        return ok_bool, cov_val, payload

    def eval_sample(self, sample: Any, *args, **kwargs):
        ok, cov, _payload = self._eval_one(sample)
        return {"passed": ok, "evidence_coverage": cov}

    def run(self, recorder, *args, **kwargs):
        n = 0
        p = 0
        cov_sum = 0.0
        for s in self._iter_samples():
            n += 1
            ok, cov, _payload = self._eval_one(s)
            if ok:
                p += 1
            cov_sum += cov
        pass_rate = (p / n) if n else 0.0
        cov_avg = (cov_sum / n) if n else 0.0
        return {"n_samples": n, "n_passed": p, "pass_rate": pass_rate, "evidence_coverage": cov_avg}
