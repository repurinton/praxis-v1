from __future__ import annotations

import os
import re
import random
from pathlib import Path
from typing import Optional

from praxis_core.claims import Claim, ClaimType
from praxis_core.dataset import Dataset, load_dataset
from praxis_core.evidence_store import DatasetEvidenceStore

# =============================================================================
# CLAIM TYPES (Praxis)
# =============================================================================
# The generator is responsible for emitting *Claim* objects (see src/praxis_core/claims.py)
# that are attributable to evidence (EvidenceRef) and suitable for deterministic verification.
#
# Claim.type is an enum with these supported types:
#
#   1) ClaimType.NUMERIC
#      - For scalar, testable numeric assertions.
#      - Expected fields:
#          * value: float (preferred; may be None only when intentionally testing failure modes)
#          * unit: str (e.g., "USD", "%", "days")
#          * evidence: 1+ EvidenceRef with a structured data_row when possible
#      - Examples:
#          * "Trial balance balance for Revenue is 1250000 USD."
#          * "Gross margin was 42%."
#
#   2) ClaimType.TEXTUAL
#      - For qualitative assertions that are still evidence-backed.
#      - Expected fields:
#          * value: typically None
#          * evidence: 1+ EvidenceRef with snippet/locator sufficient for a reviewer/auditor
#      - Examples:
#          * "Revenue exceeds Expenses on the trial balance."
#          * "The trial balance contains a Cash line item."
#
#   3) ClaimType.POLICY
#      - For standards/presentation assertions (GAAP/IFRS style policy statements),
#        e.g., "Revenue is recognized when control transfers", or "Cash is classified as..."
#      - Expected fields:
#          * evidence: policy memo / accounting policy note / standard citation pointer
#          * source_meta: may include standard version / jurisdiction
#      - Examples:
#          * "Revenue recognition policy conforms to ASC 606."
#
#   4) ClaimType.DERIVED
#      - For computed claims derived from other facts/claims (chain-of-evidence).
#      - Expected fields:
#          * evidence: references to the underlying source rows used for computation
#          * source_meta: include derivation formula inputs/assumptions for auditability
#      - Examples:
#          * "Operating margin = (Operating Income / Revenue) = 18.2%."
#
# Practical guidance:
# - Prefer grounding claims with EvidenceRef.data_row when sourced from structured datasets
#   (trial balance, ledgers, etc.) to enable deterministic checks (numeric agreement, coverage).
# - Use ClaimType.TEXTUAL only when a numeric representation is not appropriate.
# - Use ClaimType.POLICY and ClaimType.DERIVED to align the repo with the academic goals:
#   standards-conformance, auditability, reproducible evaluation, and governed release gating.
# =============================================================================



def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "x"


def generate_claims_from_dataset(
    dataset: Dataset,
    *,
    run_idx: int = 1,
    n_claims: int = 4,
    seed: Optional[int] = None,
) -> tuple[Claim, ...]:
    """
    Dataset-grounded claim generator.

    Design goals:
    - Backwards compatible + deterministic by default.
    - Produces a variable set of claims when (run_idx/seed/n_claims) are provided.
    - Exercises verification: run 1 includes one intentionally ungrounded claim;
      run 2+ grounds that same claim to demonstrate iteration improvement.
    """
    store = DatasetEvidenceStore(dataset)

    if seed is None:
        seed = (run_idx * 1009) + int(dataset.trial_balance.shape[0] or 0)
    rng = random.Random(seed)

    tb = dataset.trial_balance
    accounts = sorted({str(a) for a in tb["account"].tolist() if str(a).strip()})
    if not accounts:
        return (
            Claim(
                id="sample_textual_no_evidence",
                type=ClaimType.TEXTUAL,
                text="Sample claim with missing evidence (expected to fail evidence presence).",
                evidence=(),
            ),
        )

    def pick_account(preferred: list[str]) -> Optional[str]:
        pref_l = [p.lower() for p in preferred]
        for a in accounts:
            al = a.lower()
            if any(p in al for p in pref_l):
                return a
        return None

    revenue_acct = pick_account(["revenue", "sales"])
    expense_acct = pick_account(["expense", "cogs", "cost of goods"])
    cash_acct = pick_account(["cash"])

    claims: list[Claim] = []

    sample_pool = accounts[:]
    rng.shuffle(sample_pool)

    target_numeric = max(1, min(len(sample_pool), n_claims - 2))

    for acct in sample_pool[:target_numeric]:
        ev = None
        try:
            ev = store.trial_balance_account(acct)
        except Exception:
            ev = None

        value = None
        unit = "USD"
        if ev and getattr(ev, "data_row", None) and isinstance(ev.data_row, dict):
            v = ev.data_row.get("balance")
            if isinstance(v, (int, float)):
                value = float(v)

        claims.append(
            Claim(
                id=f"tb_{_slug(acct)}_balance_r{run_idx}",
                type=ClaimType.NUMERIC,
                text=f"Trial balance balance for {acct}.",
                value=value,
                unit=unit,
                evidence=(ev,) if ev else (),
            )
        )

    if revenue_acct and expense_acct:
        rev_ev = store.trial_balance_account(revenue_acct)
        exp_ev = store.trial_balance_account(expense_acct)
        claims.append(
            Claim(
                id=f"rev_gt_exp_r{run_idx}",
                type=ClaimType.TEXTUAL,
                text=f"{revenue_acct} exceeds {expense_acct} on the trial balance.",
                evidence=tuple(e for e in (rev_ev, exp_ev) if e),
            )
        )
    elif cash_acct:
        cash_ev = store.trial_balance_account(cash_acct)
        claims.append(
            Claim(
                id=f"cash_present_r{run_idx}",
                type=ClaimType.TEXTUAL,
                text=f"The trial balance contains a Cash line item ({cash_acct}).",
                evidence=(cash_ev,) if cash_ev else (),
            )
        )

    profit_evidence = ()
    if run_idx >= 2 and revenue_acct:
        rev_ev = store.trial_balance_account(revenue_acct)
        exp_ev = store.trial_balance_account(expense_acct) if expense_acct else None
        profit_evidence = tuple(e for e in (rev_ev, exp_ev) if e)

    claims.append(
        Claim(
            id=f"profit_positive_r{run_idx}",
            type=ClaimType.TEXTUAL,
            text="The company is profitable.",
            evidence=profit_evidence,
        )
    )

    return tuple(claims[: max(1, n_claims)])


def generate_sample_claims(
    dataset_path: Optional[str | Path] = None,
    *,
    run_idx: int = 1,
    n_claims: int = 4,
    seed: Optional[int] = None,
) -> tuple[Claim, ...]:
    """
    Backwards-compatible entrypoint expected by run.py and the GUI.
    """
    if dataset_path is not None:
        ds = load_dataset(Path(dataset_path))
        return generate_claims_from_dataset(ds, run_idx=run_idx, n_claims=n_claims, seed=seed)

    env_root = os.environ.get("PRAXIS_DATASET_ROOT")
    if env_root:
        p = Path(env_root)
        if p.exists():
            ds = load_dataset(p)
            return generate_claims_from_dataset(ds, run_idx=run_idx, n_claims=n_claims, seed=seed)

    default_root = Path("data") / "latest"
    if default_root.exists():
        ds = load_dataset(default_root)
        return generate_claims_from_dataset(ds, run_idx=run_idx, n_claims=n_claims, seed=seed)

    return (
        Claim(
            id="sample_textual_no_evidence",
            type=ClaimType.TEXTUAL,
            text="Sample claim with missing evidence (expected to fail evidence presence).",
            evidence=(),
        ),
    )
