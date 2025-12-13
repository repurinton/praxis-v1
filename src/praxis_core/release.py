from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from praxis_core.verification import VerificationReport, VerificationStatus


class ReleaseDecision(str, Enum):
    PROCEED = "proceed"
    HOLD = "hold"
    BLOCK = "block"


@dataclass(frozen=True)
class ReleaseOutcome:
    decision: ReleaseDecision
    reason: str


def decide_release(report: VerificationReport) -> ReleaseOutcome:
    """
    Controller-governed release logic.
    """
    if report.status == VerificationStatus.PASS:
        return ReleaseOutcome(
            decision=ReleaseDecision.PROCEED,
            reason="All verification gates passed.",
        )

    if report.status == VerificationStatus.NEEDS_REVIEW:
        return ReleaseOutcome(
            decision=ReleaseDecision.HOLD,
            reason="Verification incomplete; human review or additional evidence required.",
        )

    return ReleaseOutcome(
        decision=ReleaseDecision.BLOCK,
        reason="Verification failed; release blocked.",
    )
