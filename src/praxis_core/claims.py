from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Optional


class ClaimType(str, Enum):
    NUMERIC = "numeric"
    TEXTUAL = "textual"
    POLICY = "policy"   # e.g., GAAP/IFRS presentation statements
    DERIVED = "derived" # computed from other facts


@dataclass(frozen=True)
class EvidenceRef:
    """
    Stable pointer to evidence plus optional integrity metadata.

    source_id: stable identifier (e.g., "ledger.csv", "trial_balance.csv", "policy_memo")
    locator: where inside the source (e.g., "L10", "sheet=TB!A2:B20", "account=Revenue")
    content_hash: optional hash of the evidence payload used at runtime (for auditability)
    snippet: optional short human-readable excerpt/value for logs/debugging
    data_row: optional structured row payload (used by deterministic verification/tests)
    """
    source_id: str
    locator: str
    content_hash: Optional[str] = None
    snippet: Optional[str] = None
    data_row: Optional[dict[str, Any]] = None

    @staticmethod
    def hash_content(content: str) -> str:
        return sha256(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        # dataclasses.asdict is fine here; it will keep enums out of this class.
        return asdict(self)


@dataclass(frozen=True)
class Claim:
    """
    Atomic claim that must be attributable to evidence.
    """
    id: str
    type: ClaimType
    text: str
    value: Optional[float] = None
    unit: Optional[str] = None
    evidence: tuple[EvidenceRef, ...] = ()
    # optional producer/tool metadata for auditability
    source_meta: dict[str, Any] = None  # type: ignore[assignment]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Convert Enum to plain value for JSON serialization.
        d["type"] = self.type.value
        # Normalize source_meta default
        if d.get("source_meta") is None:
            d["source_meta"] = {}
        return d
