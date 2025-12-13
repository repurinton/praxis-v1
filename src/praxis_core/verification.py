from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Optional

from praxis_core.claims import Claim


class VerificationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True)
class ClaimCheck:
    claim_id: str
    status: VerificationStatus
    reason: str


@dataclass(frozen=True)
class VerificationReport:
    """
    Structured output that is auditable and machine-consumable by the controller.

    status: overall gate decision
    checks: per-claim results
    """
    status: VerificationStatus
    checks: tuple[ClaimCheck, ...]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        for c in d["checks"]:
            c["status"] = c["status"].value if hasattr(c["status"], "value") else c["status"]
        return d


def verify_evidence_presence(
    claims: tuple[Claim, ...],
    *,
    min_attribution_coverage: float = 1.0,
) -> VerificationReport:
    """
    Gate rule: require evidence for claims, enforcing an attribution coverage threshold.

    - If coverage >= threshold => PASS
    - If coverage > 0 but below threshold => NEEDS_REVIEW
    - If coverage == 0 and claims exist => FAIL
    """
    if not claims:
        return VerificationReport(
            status=VerificationStatus.NEEDS_REVIEW,
            checks=(),
            summary="No claims provided.",
        )

    total = len(claims)
    with_ev = sum(1 for c in claims if c.evidence and len(c.evidence) > 0)
    coverage = with_ev / total

    checks = []
    for c in claims:
        if c.evidence and len(c.evidence) > 0:
            checks.append(ClaimCheck(c.id, VerificationStatus.PASS, "Evidence present."))
        else:
            checks.append(ClaimCheck(c.id, VerificationStatus.FAIL, "Missing evidence."))

    if coverage >= min_attribution_coverage:
        overall = VerificationStatus.PASS
    elif coverage == 0.0:
        overall = VerificationStatus.FAIL
    else:
        overall = VerificationStatus.NEEDS_REVIEW

    return VerificationReport(
        status=overall,
        checks=tuple(checks),
        summary=f"evidence_coverage={coverage:.3f} ({with_ev}/{total}), threshold={min_attribution_coverage}",
    )
