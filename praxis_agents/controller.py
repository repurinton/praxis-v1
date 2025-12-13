from agents import Agent

controller_agent = Agent(
    name="PraxisController",
    instructions=(
        "You are the PraxisController agent for the Praxis repo. "
        "Be concise and practical. "
        "When asked what to build next, propose 3 concrete, repo-scoped next steps."
    ),
)