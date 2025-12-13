from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from hashlib import sha256
from typing import Any, Optional


class ClaimType(str, Enum):
    NUMERIC = "numeric"
    TEXTUAL = "textual"
    POLICY = "policy"          # e.g., GAAP/IFRS presentation statements
    DERIVED = "derived"        # computed from other facts


@dataclass(frozen=True)
class EvidenceRef:
    """
    A stable pointer to evidence plus optional integrity metadata.

    source_id: stable identifier (e.g., "ledger_csv", "trial_balance", "policy_memo")
    locator: where inside the source (e.g., "L10", "sheet=TB!A2:B20", "page=3:para=2")
    content_hash: optional hash of the evidence payload used at runtime (for auditability)
    """
    source_id: str
    locator: str
    content_hash: Optional[str] = None

    @staticmethod
    def hash_content(content: str) -> str:
        return sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Claim:
    """
    Atomic claim that must be attributable to evidence.

    id: stable identifier, assigned by producer (agent/tool)
    type: ClaimType
    text: natural language rendering of the claim
    value: numeric value when ClaimType.NUMERIC; otherwise None
    unit: optional unit for numeric claims (USD, %, etc.)
    evidence: list of EvidenceRef items supporting this claim
    """
    id: str
    type: ClaimType
    text: str
    value: Optional[float] = None
    unit: Optional[str] = None
    evidence: tuple[EvidenceRef, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Convert Enums to plain values for JSON serialization.
        d["type"] = self.type.value
        return d
