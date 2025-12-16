from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


@dataclass(frozen=True)
class Dataset:
    """
    In-memory view of a dataset run folder.

    `files` is a convenience index so other modules can reliably locate
    dataset artifacts by standard filename (e.g., 'trial_balance.csv').
    """
    root: Path
    files: Dict[str, Path]

    transactions: pd.DataFrame
    journal_entries: pd.DataFrame
    trial_balance: pd.DataFrame

    anomalies: Optional[pd.DataFrame] = None
    claims_truth: Optional[pd.DataFrame] = None


def _must(p: Path) -> Path:
    if not p.exists():
        raise FileNotFoundError(f"Missing required dataset file: {p}")
    return p


def load_dataset(root: Path) -> Dataset:
    """
    Load a dataset run directory created by scripts/build_synthetic_dataset.py.

    Required:
      - transactions.csv
      - journal_entries.csv
      - trial_balance.csv

    Optional:
      - anomalies.csv
      - claims_truth.jsonl
    """
    root = Path(root)

    tx_path = _must(root / "transactions.csv")
    je_path = _must(root / "journal_entries.csv")
    tb_path = _must(root / "trial_balance.csv")

    files = {
        "transactions.csv": tx_path,
        "journal_entries.csv": je_path,
        "trial_balance.csv": tb_path,
    }

    anomalies_path = root / "anomalies.csv"
    if anomalies_path.exists():
        files["anomalies.csv"] = anomalies_path

    claims_path = root / "claims_truth.jsonl"
    if claims_path.exists():
        files["claims_truth.jsonl"] = claims_path

    tx = pd.read_csv(tx_path)
    je = pd.read_csv(je_path)
    tb = pd.read_csv(tb_path)

    anomalies = pd.read_csv(anomalies_path) if anomalies_path.exists() else None
    claims_truth = pd.read_json(claims_path, lines=True) if claims_path.exists() else None

    return Dataset(
        root=root,
        files=files,
        transactions=tx,
        journal_entries=je,
        trial_balance=tb,
        anomalies=anomalies,
        claims_truth=claims_truth,
    )
