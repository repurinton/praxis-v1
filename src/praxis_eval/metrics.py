from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class EvalResult:
    """Single evaluation result with a numeric score in [0,1] when applicable."""
    name: str
    score: Optional[float]  # None when not computed
    details: str


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def numeric_agreement(
    expected: dict[str, float],
    predicted: dict[str, float],
    *,
    tolerance: float = 0.0,
) -> EvalResult:
    """
    Computes line-item numeric agreement between expected and predicted values.

    Agreement definition:
    - For each key in expected:
      - If missing in predicted => mismatch.
      - Else compare absolute difference <= tolerance.
    Score = matches / total_expected.
    """
    if not expected:
        return EvalResult("numeric_agreement", None, "No expected items provided.")

    total = 0
    matches = 0
    missing = []

    for k, v in expected.items():
        total += 1
        if k not in predicted:
            missing.append(k)
            continue
        if abs(predicted[k] - v) <= tolerance:
            matches += 1

    score = matches / total
    details = (
        f"matches={matches}/{total}, tolerance={tolerance}, "
        f"missing={len(missing)}"
        + (f" ({', '.join(missing[:5])}{'...' if len(missing) > 5 else ''})" if missing else "")
    )
    return EvalResult("numeric_agreement", clamp01(score), details)


def attribution_coverage(
    claims: Iterable[dict],
    *,
    evidence_field: str = "evidence",
) -> EvalResult:
    """
    Computes share of claims that include non-empty evidence.

    Expected claim shape (minimal):
      {"text": "...", "evidence": ["source_id:loc", ...]}
    Score = claims_with_evidence / total_claims.
    """
    claims_list = list(claims)
    if not claims_list:
        return EvalResult("attribution_coverage", None, "No claims provided.")

    total = len(claims_list)
    covered = 0
    missing_idx = []

    for i, c in enumerate(claims_list):
        ev = c.get(evidence_field)
        if isinstance(ev, list) and len(ev) > 0 and all(isinstance(x, str) and x.strip() for x in ev):
            covered += 1
        else:
            missing_idx.append(i)

    score = covered / total
    details = f"covered={covered}/{total}, missing_indexes={missing_idx[:10]}{'...' if len(missing_idx) > 10 else ''}"
    return EvalResult("attribution_coverage", clamp01(score), details)


def placeholder_factscore(
    supported_sentences: int,
    total_sentences: int,
) -> EvalResult:
    """
    Placeholder for a sentence-level factuality metric (e.g., FActScore).
    Until we implement retrieval+verification, we represent it as:
      supported_sentences / total_sentences
    """
    if total_sentences <= 0:
        return EvalResult("factscore", None, "total_sentences must be > 0.")
    score = supported_sentences / total_sentences
    return EvalResult("factscore", clamp01(score), f"supported={supported_sentences}/{total_sentences}")
