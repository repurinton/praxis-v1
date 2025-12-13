from pathlib import Path

from dotenv import load_dotenv
from agents import Runner

from praxis_agents.controller import controller_agent
from praxis_agents.planner import planner_agent
from praxis_core.generator_stub import generate_sample_claims
from praxis_core.verification import verify_evidence_presence



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
        "Select the single next best small, reversible step to implement in this repo.\n\n"
        "=== ROADMAP ===\n"
        f"{getattr(roadmap, 'final_output', getattr(roadmap, 'output', str(roadmap)))}\n"
        "=== END ROADMAP ===\n"
    )
    decision = Runner.run_sync(controller_agent, input=controller_input)

    print("=== PraxisPlanner Roadmap ===")
    print_result(roadmap)
    print("\n=== PraxisController Decision ===")
    print_result(decision)

    # NOTE: Next milestone will inject:
    # Generator -> Claims -> verify_evidence_presence() -> Controller release decision

    print("\n=== Generator → Verification Demo ===")

    claims = generate_sample_claims()
    report = verify_evidence_presence(claims, min_attribution_coverage=1.0)

    print("Verification status:", report.status.value)
    print("Summary:", report.summary)
    for c in report.checks:
        print(f"- {c.claim_id}: {c.status.value} ({c.reason})")



if __name__ == "__main__":
    main()
