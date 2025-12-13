from __future__ import annotations

from typing import Iterable, Mapping, Any

from praxis_core.claims import Claim


def claims_to_metric_shape(claims: Iterable[Claim]) -> list[Mapping[str, Any]]:
    """
    Convert Claim objects into the minimal dict shape expected by attribution_coverage().
    """
    out = []
    for c in claims:
        out.append(
            {
                "text": c.text,
                "evidence": [f"{e.source_id}:{e.locator}" for e in c.evidence],
            }
        )
    return out
