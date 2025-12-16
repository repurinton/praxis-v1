from __future__ import annotations

from pathlib import Path

from praxis_core.dataset import load_dataset
from praxis_core.evidence_store import DatasetEvidenceStore


def _write_min_dataset(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    (root / "transactions.csv").write_text(
        "txn_id,company_id,date,amount,currency,type\n"
        "T1,C001,2024-01-01,100,USD,revenue\n"
    )

    (root / "journal_entries.csv").write_text(
        "txn_id,account,debit,credit\n"
        "T1,Accounts Receivable,100,0\n"
        "T1,Revenue,0,100\n"
    )

    # IMPORTANT: match what DatasetEvidenceStore expects: account + amount
    (root / "trial_balance.csv").write_text(
        "account,amount\n"
        "Revenue,100\n"
        "COGS,60\n"
    )

    (root / "manifest.json").write_text("{}")


def test_dataset_evidence_store_resolves_trial_balance(tmp_path: Path):
    d = tmp_path / "dataset"
    _write_min_dataset(d)

    dataset = load_dataset(d)
    store = DatasetEvidenceStore(dataset)

    ev = store.trial_balance_account("Revenue")
    assert ev is not None
    assert ev.data_row is not None
    assert ev.data_row["account"] == "Revenue"
    assert float(ev.data_row["amount"]) == 100.0


def test_dataset_evidence_store_missing_account(tmp_path: Path):
    d = tmp_path / "dataset"
    _write_min_dataset(d)

    dataset = load_dataset(d)
    store = DatasetEvidenceStore(dataset)

    ev = store.trial_balance_account("DoesNotExist")
    assert ev is None
