#!/bin/bash
# Start the FactoryLM Serena Agent with Agno web UI
# Requires: serena[agno] installed in ~/Desktop/serena/.venv
# UI: connect Agent UI at http://localhost:3000 to http://localhost:7777

SERENA_ROOT="C:/Users/hharp/OneDrive/Desktop/serena"
FACTORYLM_ROOT="C:/Users/hharp/OneDrive/Desktop/FactoryLM"

cd "$SERENA_ROOT" || exit 1

export SERENA_ROOT

doppler run -p factorylm -c dev -- \
  uv run python "$FACTORYLM_ROOT/agents/serena_agent.py" \
  --project "$FACTORYLM_ROOT"
