#!/usr/bin/env python3
"""Fix ultron openclaw config: add compaction floor, verify model settings."""
import json

CONFIG = "/root/.openclaw/openclaw.json"

with open(CONFIG) as f:
    c = json.load(f)

# Fix compaction - add reserveTokensFloor to prevent context overflow
c["agents"]["defaults"]["compaction"] = {
    "mode": "safeguard",
    "reserveTokensFloor": 4000
}

# Verify model config (Claude Code already fixed this)
model = c["agents"]["defaults"]["model"]
print(f"Primary: {model['primary']}")
print(f"Fallbacks: {model.get('fallbacks', [])}")
print(f"Compaction: {c['agents']['defaults']['compaction']}")

with open(CONFIG, "w") as f:
    json.dump(c, f, indent=2)

print("Config saved OK")
