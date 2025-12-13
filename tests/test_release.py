from praxis_core.release import decide_release, ReleaseDecision
from praxis_core.verification import (
    VerificationReport,
    VerificationStatus,
    ClaimCheck,
)


def test_release_proceed():
    report = VerificationReport(
        status=VerificationStatus.PASS,
        checks=(),
        summary="ok",
    )
    r = decide_release(report)
    assert r.decision == ReleaseDecision.PROCEED


def test_release_hold():
    report = VerificationReport(
        status=VerificationStatus.NEEDS_REVIEW,
        checks=(),
        summary="partial",
    )
    r = decide_release(report)
    assert r.decision == ReleaseDecision.HOLD


def test_release_block():
    report = VerificationReport(
        status=VerificationStatus.FAIL,
        checks=(),
        summary="fail",
    )
    r = decide_release(report)
    assert r.decision == ReleaseDecision.BLOCK
