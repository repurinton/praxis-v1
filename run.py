from pathlib import Path
import os

from dotenv import load_dotenv
from agents import Runner

from praxis_agents.controller import controller_agent
from praxis_agents.planner import planner_agent
from praxis_core.generator_stub import generate_sample_claims
from praxis_core.verification import verify_evidence_presence
from praxis_core.release import decide_release
from praxis_core.run_artifacts import build_run_artifact, write_run_artifact


def read_plan_text() -> str:
    plan_path = Path(__file__).parent / "docs" / "praxis_plan.md"
    if not plan_path.exists():
        raise FileNotFoundError(
            f"Missing {plan_path}. Create docs/praxis_plan.md from the Praxis PDF extract."
        )
    return plan_path.read_text(encoding="utf-8")


def print_result(result) -> None:
    if hasattr(result, "final_output"):
        print(result.final_output)
    elif hasattr(result, "output"):
        print(result.output)
    else:
        print(result)


def main() -> None:
    load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

    plan_text = read_plan_text()

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY missing; skipping Planner/Controller agent calls.")
    else:
        try:
            # 1) Planner produces roadmap
            planner_input = (
                "Using the following Praxis plan context, produce the roadmap.\n\n"
                "=== PRAXIS PLAN CONTEXT ===\n"
                f"{plan_text}\n"
                "=== END CONTEXT ===\n"
            )
            roadmap = Runner.run_sync(planner_agent, input=planner_input)

            # 2) Controller selects next step
            controller_input = (
                "You are given a roadmap produced by PraxisPlanner.\n"
                "Select the single next best small, reversible step to implement in this repo.\n"
                "Constraints:\n"
                "- Do NOT create a new top-level claims.py.\n"
                "- The canonical Claim/Evidence dataclasses already live in src/praxis_core/claims.py.\n"
                "- Propose changes only within the existing src/praxis_core/* modules unless explicitly instructed.\n\n"
                "=== ROADMAP ===\n"
                f"{getattr(roadmap, 'final_output', getattr(roadmap, 'output', str(roadmap)))}\n"
                "=== END ROADMAP ===\n"
            )
            decision = Runner.run_sync(controller_agent, input=controller_input)

            print("=== PraxisPlanner Roadmap ===")
            print_result(roadmap)
            print("\n=== PraxisController Decision ===")
            print_result(decision)
        except Exception as e:
            print("Planner/Controller run failed:", e)

    # NOTE: Next milestone will inject:
    # Generator -> Claims -> verify_evidence_presence() -> Controller release decision

    print("\n=== Generator → Verification → Release Demo ===")

    dataset_root = os.environ.get("PRAXIS_DATASET_ROOT")
    if dataset_root:
        claims = generate_sample_claims(dataset_root)
    else:
        default_root = Path("data") / "synthetic"
        claims = generate_sample_claims(default_root if default_root.exists() else None)

    report = verify_evidence_presence(claims, min_attribution_coverage=1.0)
    outcome = decide_release(report)

    # Persist immutable run artifact (does not affect gating)
    artifact = build_run_artifact(
        run_source='run.py',
        dataset_root=str(dataset_root) if dataset_root else None,
        min_attribution_coverage=1.0,
        planner_output=getattr(roadmap, 'final_output', getattr(roadmap, 'output', None)) if 'roadmap' in locals() else None,
        controller_output=getattr(decision, 'final_output', getattr(decision, 'output', None)) if 'decision' in locals() else None,
        claims=claims,
        verification_report=report,
        release_outcome=outcome,
        extra={'cwd': str(Path().resolve())},
    )
    out_path = write_run_artifact(artifact)
    print('Wrote run artifact:', out_path)

    print("Verification status:", report.status.value)
    print("Release decision:", outcome.decision.value)
    print("Reason:", outcome.reason)

    print("Summary:", report.summary)
    for c in report.checks:
        print(f"- {c.claim_id}: {c.status.value} ({c.reason})")


if __name__ == "__main__":
    main()
