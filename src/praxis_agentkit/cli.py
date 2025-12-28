from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

if os.environ.get("PRAXIS_DISABLE_TRACING", "1") == "1":
    os.environ.setdefault("OTEL_TRACES_EXPORTER", "none")
    os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")
    os.environ.setdefault("OTEL_LOGS_EXPORTER", "none")
from agents import Agent, Runner

from praxis_agentkit.config import load_agent_spec


def _agent_from_spec(spec_path: str, model: Optional[str]) -> Agent:
    spec = load_agent_spec(spec_path)
    m = model or spec.model or os.environ.get("PRAXIS_MODEL") or os.environ.get("OPENAI_MODEL")
    kwargs = {"name": spec.name, "instructions": spec.instructions}
    if m:
        kwargs["model"] = m
    return Agent(**kwargs)


def _read_plan_text() -> str:
    plan_path = Path("docs") / "praxis_plan.md"
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing {plan_path}. Create docs/praxis_plan.md from the Praxis PDF extract.")
    return plan_path.read_text(encoding="utf-8")


def _print_result(result) -> None:
    if hasattr(result, "final_output"):
        print(result.final_output)
    elif hasattr(result, "output"):
        print(result.output)
    else:
        print(result)


def main() -> int:
    ap = argparse.ArgumentParser(prog="praxis-run")
    ap.add_argument("--env-file", default=".env")
    ap.add_argument("--model", default=None)
    ap.add_argument("--agents-dir", default=str(Path("agentkit") / "agents"))
    ap.add_argument("--goal", default="Select the next best small, reversible implementation step.")
    ap.add_argument("--plan-file", default=str(Path("docs") / "praxis_plan.md"))
    ap.add_argument("--mode", choices=["planner", "controller", "full", "demo"], default="full")
    args = ap.parse_args()

    load_dotenv(dotenv_path=Path(args.env_file))

    agents_dir = Path(args.agents_dir)
    planner_path = agents_dir / "planner.yaml"
    controller_path = agents_dir / "controller.yaml"

    if args.mode == "demo":
        from praxis_core.generator_stub import generate_sample_claims
        from praxis_core.verification import verify_evidence_presence
        from praxis_core.release import decide_release

        dataset_root = os.environ.get("PRAXIS_DATASET_ROOT")
        if dataset_root:
            claims = generate_sample_claims(dataset_root)
        else:
            default_root = Path("data") / "synthetic"
            claims = generate_sample_claims(default_root if default_root.exists() else None)

        report = verify_evidence_presence(claims, min_attribution_coverage=1.0)
        outcome = decide_release(report)

        print("Verification status:", report.status.value)
        print("Release decision:", outcome.decision.value)
        print("Reason:", outcome.reason)
        print("Summary:", report.summary)
        for c in report.checks:
            print(f"- {c.claim_id}: {c.status.value} ({c.reason})")
        return 0

    plan_text = Path(args.plan_file).read_text(encoding="utf-8") if Path(args.plan_file).exists() else _read_plan_text()

    planner_agent = _agent_from_spec(str(planner_path), args.model)
    planner_input = (
        "Using the following Praxis plan context, produce the roadmap.\n\n"
        "=== PRAXIS PLAN CONTEXT ===\n"
        f"{plan_text}\n"
        "=== END CONTEXT ===\n"
    )
    roadmap = Runner.run_sync(planner_agent, input=planner_input)

    if args.mode == "planner":
        _print_result(roadmap)
        return 0

    controller_agent = _agent_from_spec(str(controller_path), args.model)
    controller_input = (
        "You are given a roadmap produced by PraxisPlanner.\n"
        f"{args.goal}\n"
        "Constraints:\n"
        "- Do NOT create a new top-level claims.py.\n"
        "- The canonical Claim/Evidence dataclasses already live in src/praxis_core/claims.py.\n"
        "- Propose changes only within the existing src/praxis_core/* modules unless explicitly instructed.\n\n"
        "=== ROADMAP ===\n"
        f"{getattr(roadmap, 'final_output', getattr(roadmap, 'output', str(roadmap)))}\n"
        "=== END ROADMAP ===\n"
    )
    decision = Runner.run_sync(controller_agent, input=controller_input)

    if args.mode in ("controller", "full"):
        print("=== PraxisPlanner Roadmap ===")
        _print_result(roadmap)
        print("\n=== PraxisController Decision ===")
        _print_result(decision)

    return 0
