"""FactoryLM Serena Agent — Agno-powered web UI for codebase navigation.

Launch via: doppler run -p factorylm -c dev -- uv run python agents/serena_agent.py --project .
Requires: serena[agno] installed in Desktop/serena venv.
UI: connect Agent UI at http://localhost:3000 to http://localhost:7777
"""
import sys
from pathlib import Path

# Add the serena source to path so we can import it
SERENA_ROOT = Path(__file__).resolve().parent.parent.parent / "serena"
if SERENA_ROOT.exists():
    sys.path.insert(0, str(SERENA_ROOT / "src"))

from agno.models.anthropic.claude import Claude
from agno.os import AgentOS
from sensai.util import logging as sensai_logging

from serena.agno import SerenaAgnoAgentProvider

if __name__ == "__main__":
    sensai_logging.configure(level=sensai_logging.INFO)

model = Claude(id="claude-sonnet-4-20250514")

serena_agent = SerenaAgnoAgentProvider.get_agent(model)

agent_os = AgentOS(
    description="FactoryLM coding assistant — industrial AI codebase navigation",
    id="factorylm-serena",
    agents=[serena_agent],
)

app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="serena_agent:app", reload=False)
