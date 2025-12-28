from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass(frozen=True)
class AgentSpec:
    name: str
    instructions: str
    model: Optional[str] = None


def load_agent_spec(path: str | Path) -> AgentSpec:
    p = Path(path)
    obj: Dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"Agent spec must be a mapping: {p}")
    name = str(obj.get("name", "")).strip()
    instructions = str(obj.get("instructions", "")).strip()
    model = obj.get("model")
    if not name or not instructions:
        raise ValueError(f"Agent spec missing name/instructions: {p}")
    return AgentSpec(name=name, instructions=instructions, model=str(model).strip() if model else None)
