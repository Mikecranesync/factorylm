import json

path = "/root/.openclaw/agents/main/agent/auth-profiles.json"
with open(path) as f:
    d = json.load(f)

d["profiles"]["anthropic:api-key"] = {
    "type": "api-key",
    "provider": "anthropic",
    "access": "[REDACTED:anthropic-api-key]"
}
d["lastGood"]["anthropic"] = "anthropic:api-key"
d["usageStats"] = {}

with open(path, "w") as f:
    json.dump(d, f, indent=2)

print("VPS key updated")
