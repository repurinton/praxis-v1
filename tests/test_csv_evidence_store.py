from pathlib import Path

from praxis_core.evidence_store import CSVEvidenceStore


def test_csv_evidence_store_resolves_numeric(tmp_path: Path):
    p = tmp_path / "trial_balance.csv"
    p.write_text("account,amount\nRevenue,100\nCOGS,60\n")

    store = CSVEvidenceStore(p)

    ev = store.get_numeric("Revenue")
    assert ev is not None
    assert ev.source_id == "trial_balance.csv"
    assert ev.locator == "account=Revenue"
    assert ev.content_hash is not None

    missing = store.get_numeric("DoesNotExist")
    assert missing is None
