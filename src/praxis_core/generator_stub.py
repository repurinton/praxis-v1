from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from praxis_core.claims import Claim, ClaimType
from praxis_core.dataset import Dataset, load_dataset
from praxis_core.evidence_store import DatasetEvidenceStore


def generate_claims_from_dataset(dataset: Dataset) -> tuple[Claim, ...]:
    """
    Deterministic, dataset-grounded claim generator.

    Intentionally includes at least one claim with missing evidence to exercise
    verification behavior in demos/tests.
    """
    store = DatasetEvidenceStore(dataset)

    revenue_ev = None
    try:
        revenue_ev = store.trial_balance_account("Revenue")
    except Exception:
        # If the dataset doesn't contain Revenue, keep deterministic behavior:
        # the claim will carry no evidence and should fail evidence presence checks.
        revenue_ev = None

    claims = [
        Claim(
            id="rev_total",
            type=ClaimType.NUMERIC,
            text="Total revenue reported in the trial balance.",
            value=None,
            unit="USD",
            evidence=(revenue_ev,) if revenue_ev else (),
        ),
        Claim(
            id="profit_positive",
            type=ClaimType.TEXTUAL,
            text="The company is profitable.",
            evidence=(),  # intentionally missing
        ),
    ]
    return tuple(claims)


def generate_sample_claims(dataset_path: Optional[str | Path] = None) -> tuple[Claim, ...]:
    """
    Backwards-compatible entrypoint expected by run.py.

    If a dataset path is available (arg, env var, or default folder), generate
    dataset-grounded claims; otherwise return deterministic placeholder claims.
    """
    # 1) Explicit argument
    if dataset_path is not None:
        ds = load_dataset(Path(dataset_path))
        return generate_claims_from_dataset(ds)

    # 2) Environment variable
    env_root = os.environ.get("PRAXIS_DATASET_ROOT")
    if env_root:
        p = Path(env_root)
        if p.exists():
            ds = load_dataset(p)
            return generate_claims_from_dataset(ds)

    # 3) Conventional default (only if present)
    default_root = Path("data") / "latest"
    if default_root.exists():
        ds = load_dataset(default_root)
        return generate_claims_from_dataset(ds)

    # 4) Fallback: deterministic claims with no evidence
    return (
        Claim(
            id="sample_textual_no_evidence",
            type=ClaimType.TEXTUAL,
            text="Sample claim with missing evidence (expected to fail evidence presence).",
            evidence=(),
        ),
    )
