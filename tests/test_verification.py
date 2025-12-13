from praxis_core.claims import Claim, ClaimType, EvidenceRef
from praxis_core.verification import VerificationStatus, verify_evidence_presence


def test_verify_pass_when_all_claims_have_evidence():
    claims = (
        Claim(
            id="c1",
            type=ClaimType.TEXTUAL,
            text="Revenue increased.",
            evidence=(EvidenceRef(source_id="tb", locator="A1"),),
        ),
        Claim(
            id="c2",
            type=ClaimType.NUMERIC,
            text="Revenue was 100 USD.",
            value=100.0,
            unit="USD",
            evidence=(EvidenceRef(source_id="tb", locator="A2"),),
        ),
    )
    r = verify_evidence_presence(claims, min_attribution_coverage=1.0)
    assert r.status == VerificationStatus.PASS


def test_verify_needs_review_when_partial_coverage():
    claims = (
        Claim(
            id="c1",
            type=ClaimType.TEXTUAL,
            text="Revenue increased.",
            evidence=(EvidenceRef(source_id="tb", locator="A1"),),
        ),
        Claim(
            id="c2",
            type=ClaimType.NUMERIC,
            text="Revenue was 100 USD.",
            value=100.0,
            unit="USD",
            evidence=(),
        ),
    )
    r = verify_evidence_presence(claims, min_attribution_coverage=1.0)
    assert r.status == VerificationStatus.NEEDS_REVIEW


def test_verify_fail_when_no_claims_have_evidence():
    claims = (
        Claim(id="c1", type=ClaimType.TEXTUAL, text="Statement.", evidence=()),
        Claim(id="c2", type=ClaimType.TEXTUAL, text="Statement 2.", evidence=()),
    )
    r = verify_evidence_presence(claims, min_attribution_coverage=0.5)
    assert r.status == VerificationStatus.FAIL
