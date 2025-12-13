from __future__ import annotations

from agents import Agent


generator_agent = Agent(
    name="PraxisGenerator",
    instructions=(
        "You are PraxisGenerator.\n"
        "Your job is to produce structured claims, not prose.\n"
        "Each claim must include:\n"
        "- id\n"
        "- type (textual or numeric)\n"
        "- text\n"
        "- optional value/unit\n"
        "- evidence references when available\n\n"
        "For now, produce a small set of example claims, some with evidence and some without, "
        "so the verification gate can be exercised.\n"
        "Output claims in JSON form."
    ),
)
