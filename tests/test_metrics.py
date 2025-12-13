from praxis_eval.metrics import (
    attribution_coverage,
    numeric_agreement,
    placeholder_factscore,
)


def test_numeric_agreement_exact():
    expected = {"rev": 100.0, "cogs": 60.0}
    predicted = {"rev": 100.0, "cogs": 60.0}
    r = numeric_agreement(expected, predicted)
    assert r.score == 1.0


def test_numeric_agreement_missing_key():
    expected = {"rev": 100.0, "cogs": 60.0}
    predicted = {"rev": 100.0}
    r = numeric_agreement(expected, predicted)
    assert r.score == 0.5


def test_attribution_coverage():
    claims = [
        {"text": "Revenue was 100.", "evidence": ["ledger.csv:L10"]},
        {"text": "COGS was 60.", "evidence": []},
    ]
    r = attribution_coverage(claims)
    assert r.score == 0.5


def test_placeholder_factscore():
    r = placeholder_factscore(8, 10)
    assert r.score == 0.8
