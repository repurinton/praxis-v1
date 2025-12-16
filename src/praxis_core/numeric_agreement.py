from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NumericAgreementResult:
    ok: bool
    claim_value: float
    evidence_value: float
    abs_diff: float
    rel_diff: Optional[float]
    abs_tol: float
    rel_tol: float
    reason: str


def verify_numeric_agreement(
    *,
    claim_value: float,
    evidence_value: float,
    abs_tol: float = 0.01,
    rel_tol: float = 0.01,
) -> NumericAgreementResult:
    """
    Deterministic numeric agreement check.

    Passes if either:
      - absolute difference <= abs_tol
      - relative difference <= rel_tol

    This function is intentionally pure and auditable.
    """
    cv = float(claim_value)
    ev = float(evidence_value)

    abs_diff = abs(cv - ev)

    scale = max(abs(ev), 1e-12)
    rel_diff = abs_diff / scale if scale > 0 else None

    abs_ok = abs_diff <= abs_tol
    rel_ok = rel_diff is not None and rel_diff <= rel_tol

    ok = abs_ok or rel_ok

    if abs_ok:
        reason = "abs_ok"
    elif rel_ok:
        reason = "rel_ok"
    else:
        reason = (
            f"mismatch(abs_diff={abs_diff:.6g} > abs_tol={abs_tol:.6g}, "
            f"rel_diff={rel_diff:.6g} > rel_tol={rel_tol:.6g})"
        )

    return NumericAgreementResult(
        ok=ok,
        claim_value=cv,
        evidence_value=ev,
        abs_diff=abs_diff,
        rel_diff=rel_diff,
        abs_tol=float(abs_tol),
        rel_tol=float(rel_tol),
        reason=reason,
    )
