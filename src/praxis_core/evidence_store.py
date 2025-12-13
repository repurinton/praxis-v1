from __future__ import annotations

import csv
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
        Resolve a numeric account value from a CSV with schema:
        account,amount

        Returns an EvidenceRef if found, otherwise None.
        """
        with self.path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("account") == account:
                    content = f"{row['account']}={row['amount']}"
                    return EvidenceRef(
                        source_id=self.path.name,
                        locator=f"account={account}",
                        content_hash=EvidenceRef.hash_content(content),
                    )
        return None
