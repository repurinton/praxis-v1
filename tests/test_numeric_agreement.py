from __future__ import annotations

from pathlib import Path

from praxis_core.dataset import load_dataset
from praxis_core.verification import verify_numeric_agreement


def _write_min_dataset(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    # Your loader requires transactions.csv (per stack trace).
    (root / "transactions.csv").write_text(
        "txn_id,company_id,date,amount,currency,type\n"
        "T1,C001,2024-01-01,100,USD,revenue\n"
    )

    # Most repos also require journal_entries.csv; keep it minimal and consistent.
    (root / "journal_entries.csv").write_text(
        "txn_id,account,debit,credit\n"
        "T1,Accounts Receivable,100,0\n"
        "T1,Revenue,0,100\n"
    )

    # IMPORTANT: Your evidence store expects 'amount' on trial_balance rows.
    (root / "trial_balance.csv").write_text(
        "account,amount\n"
        "Revenue,100\n"
        "COGS,60\n"
    )

    # Some code paths read manifest.json; harmless to include.
    (root / "manifest.json").write_text("{}")


def test_numeric_agreement_pass(tmp_path: Path):
    d = tmp_path / "run"
    _write_min_dataset(d)

    dataset = load_dataset(d)

    # Example: claim matches evidence
    r = verify_numeric_agreement(
        claim_value=100.0,
        evidence_value=100.0,
        abs_tol=0.01,
        rel_tol=0.01,
    )
    assert r.ok is True


def test_numeric_agreement_fail(tmp_path: Path):
    d = tmp_path / "run"
    _write_min_dataset(d)

    dataset = load_dataset(d)

    # Example: claim does not match evidence
    r = verify_numeric_agreement(
        claim_value=100.0,
        evidence_value=80.0,
        abs_tol=0.01,
        rel_tol=0.01,
    )
    assert r.ok is False
