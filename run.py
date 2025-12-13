from pathlib import Path

from dotenv import load_dotenv

# OpenAI Agents SDK (pip: openai-agents)
from agents import Runner

# Local project code
from praxis_agents.controller import controller_agent


load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

result = Runner.run_sync(
    controller_agent,
    input="Say hello, then list the next 3 concrete things you can help build in this repo.",
)

if hasattr(result, "final_output"):
    print(result.final_output)
elif hasattr(result, "output"):
    print(result.output)
else:
    print(result)
