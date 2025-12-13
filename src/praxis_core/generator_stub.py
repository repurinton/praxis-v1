from praxis_core.claims import Claim, ClaimType, EvidenceRef


def generate_sample_claims() -> tuple[Claim, ...]:
    """
    Deterministic generator stub.
    This simulates an LLM or agent producing claims.
    """
    return (
        Claim(
            id="c1",
            type=ClaimType.NUMERIC,
            text="Revenue was 100 USD.",
            value=100.0,
            unit="USD",
            evidence=(EvidenceRef(source_id="trial_balance", locator="A10"),),
        ),
        Claim(
            id="c2",
            type=ClaimType.TEXTUAL,
            text="Revenue increased quarter-over-quarter.",
            evidence=(),  # Missing evidence on purpose
        ),
    )
