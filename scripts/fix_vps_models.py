import json

path = "/root/.openclaw/openclaw.json"
with open(path) as f:
    d = json.load(f)

# Anthropic works but rate-limited on Opus - use Sonnet as primary (cheaper, higher limits)
# Gemini as first fallback (when Google billing is resolved)
d["agents"]["defaults"]["model"]["primary"] = "anthropic/claude-sonnet-4-20250514"
d["agents"]["defaults"]["model"]["fallbacks"] = [
    "google/gemini-2.5-flash",
    "anthropic/claude-opus-4-5"
]

with open(path, "w") as f:
    json.dump(d, f, indent=2)

print("DONE: primary=claude-sonnet-4, fallbacks=[gemini-2.5-flash, claude-opus-4-5]")
