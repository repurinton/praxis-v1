from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from praxis_core.claims import EvidenceRef


class CSVEvidenceStore:
    """
    Deterministic evidence resolver for CSV-backed datasets.

    This class does NOT interpret meaning — it only resolves
    concrete evidence references in a reproducible way.
    """

    def __init__(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(path)
        self.path = path

    def get_numeric(self, account: str) -> Optional[EvidenceRef]:
        """
        Resolve a numeric value for a given account from this CSV.

        Expected CSV shapes supported:
          - trial_balance.csv: account,balance   (or account,amount)
          - other ledgers: account,amount
          - fallback: first numeric column in the matched row

        Returns:
          EvidenceRef or None if the account is not present.
        """
        # Load rows
        with self.path.open("r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return None

        # Normalize strings for matching
        def norm(s: str) -> str:
            return (s or "").strip().lower()

        target = norm(account)

        match = None
        for r in rows:
            acct_val = None
            for k in r.keys():
                if norm(k) == "account":
                    acct_val = r.get(k)
                    break
            if acct_val is not None and norm(acct_val) == target:
                match = r
                break

        if match is None:
            return None

        # Parse numeric values robustly
        def parse_float(v) -> Optional[float]:
            if v is None:
                return None
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip()
            if s == "":
                return None
            s = s.replace(",", "")
            try:
                return float(s)
            except ValueError:
                return None

        # Prefer common numeric fields
        value = None
        chosen_field = None
        for preferred in ("amount", "balance", "value"):
            for k in match.keys():
                if norm(k) == preferred:
                    value = parse_float(match.get(k))
                    chosen_field = k
                    break
            if value is not None:
                break

        # Fallback: first numeric field (excluding account)
        if value is None:
            for k, v in match.items():
                if norm(k) == "account":
                    continue
                fv = parse_float(v)
                if fv is not None:
                    value = fv
                    chosen_field = k
                    break

        if value is None:
            raise KeyError(
                f"No numeric field found for account '{account}' in {self.path.name}"
            )

        # Build audit hash from full row
        row_json = json.dumps(match, sort_keys=True, default=str)
        content_hash = EvidenceRef.hash_content(row_json)

        snippet = f"{account} {chosen_field}={value}"

        return EvidenceRef(
            source_id=self.path.name,
            locator=f"account={account}",
            content_hash=content_hash,
            snippet=snippet,
            data_row=match,  # REQUIRED for downstream verification/tests
        )


# ---------------------------------------------------------------------------
# DatasetEvidenceStore (public API expected by tests and higher layers)
# ---------------------------------------------------------------------------

class DatasetEvidenceStore:
    """
    Authoritative evidence resolver bound to a Dataset instance.

    This is the ONLY class higher layers should use.
    """

    def __init__(self, dataset):
        self.dataset = dataset

    def require_csv(self, filename: str) -> CSVEvidenceStore:
        """
        Fetch a CSV evidence store from the dataset.
        Fails loudly if the file is missing.
        """
        if not hasattr(self.dataset, "files") or self.dataset.files is None:
            raise AttributeError(
                "Dataset is missing required attribute 'files' (dict[str, Path])."
            )

        if filename not in self.dataset.files:
            raise FileNotFoundError(f"Missing required dataset file: {filename}")

        return CSVEvidenceStore(self.dataset.files[filename])

    def trial_balance_account(self, account: str) -> Optional[EvidenceRef]:
        """
        Resolve an account balance from trial_balance.csv.
        """
        store = self.require_csv("trial_balance.csv")
        return store.get_numeric(account=account)
