import json

path = "/root/.openclaw/openclaw.json"
with open(path) as f:
    d = json.load(f)

# Fix gateway bind to loopback for health checks
d["gateway"]["bind"] = "loopback"

# Disable otel plugin that's missing deps
if "diagnostics-otel" in d.get("plugins", {}).get("entries", {}):
    d["plugins"]["entries"]["diagnostics-otel"]["enabled"] = False

with open(path, "w") as f:
    json.dump(d, f, indent=2)

print("FIXED: bind=loopback, disabled diagnostics-otel")
