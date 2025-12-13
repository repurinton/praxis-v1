from praxis_core.claims import Claim, ClaimType, EvidenceRef
from praxis_eval.adapters import claims_to_metric_shape
from praxis_eval.metrics import attribution_coverage


def test_claim_serialization_and_attribution():
    c1 = Claim(
        id="c1",
        type=ClaimType.TEXTUAL,
        text="Revenue increased quarter-over-quarter.",
        evidence=(EvidenceRef(source_id="mgmt_report", locator="page=2:para=1"),),
    )
    c2 = Claim(
        id="c2",
        type=ClaimType.NUMERIC,
        text="Revenue was 100.0 USD.",
        value=100.0,
        unit="USD",
        evidence=(),
    )

    shaped = claims_to_metric_shape([c1, c2])
    r = attribution_coverage(shaped)
    assert r.score == 0.5

    d = c1.to_dict()
    assert d["type"] == "textual"
    assert d["evidence"][0]["source_id"] == "mgmt_report"
