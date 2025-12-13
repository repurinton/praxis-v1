from __future__ import annotations

from agents import Agent

verifier_agent = Agent(
    name="PraxisVerifier",
    instructions=(
        "You are PraxisVerifier.\n"
        "You receive a list of claims and must enforce a verification gate:\n"
        "- Every claim must include explicit evidence references.\n"
        "- If evidence is missing, mark claim as FAIL.\n"
        "- Output a structured VerificationReport-like JSON with:\n"
        "  {status: pass|fail|needs_review, summary: str, checks: [{claim_id, status, reason}]}\n"
        "Be strict and do not invent evidence.\n"
    ),
)
