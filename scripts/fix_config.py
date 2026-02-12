import json

path = "/root/.clawdbot/clawdbot.json"
with open(path) as f:
    d = json.load(f)

d["channels"]["telegram"]["dmPolicy"] = "allowlist"
d["channels"]["telegram"]["allowFrom"] = ["8445149012"]
d["channels"]["telegram"]["groupPolicy"] = "disabled"

with open(path, "w") as f:
    json.dump(d, f, indent=2)

print("FIXED: groupPolicy=disabled, dmPolicy=allowlist, allowFrom=8445149012")
