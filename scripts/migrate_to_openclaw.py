import json, os, shutil

old_path = "/root/.clawdbot/clawdbot.json"
new_dir = "/root/.openclaw"
new_path = os.path.join(new_dir, "openclaw.json")

# Create openclaw dir
os.makedirs(new_dir, exist_ok=True)

# Read old config
with open(old_path) as f:
    d = json.load(f)

# Update version ref
d["meta"]["lastTouchedVersion"] = "2026.2.9"

# Fix telegram security
d["channels"]["telegram"]["dmPolicy"] = "allowlist"
d["channels"]["telegram"]["allowFrom"] = ["8445149012"]
d["channels"]["telegram"]["groupPolicy"] = "disabled"

# Write new config
with open(new_path, "w") as f:
    json.dump(d, f, indent=2)

# Copy auth profiles
old_auth = "/root/.clawdbot/agents/main/agent/auth-profiles.json"
new_agent_dir = "/root/.openclaw/agents/main/agent"
os.makedirs(new_agent_dir, exist_ok=True)
if os.path.exists(old_auth):
    shutil.copy2(old_auth, os.path.join(new_agent_dir, "auth-profiles.json"))
    print("Copied auth-profiles.json")

# Copy sessions
old_sessions = "/root/.clawdbot/agents/main/sessions"
new_sessions = "/root/.openclaw/agents/main/sessions"
if os.path.exists(old_sessions):
    shutil.copytree(old_sessions, new_sessions, dirs_exist_ok=True)
    print("Copied sessions")

# Copy credentials
old_creds = "/root/.clawdbot/credentials"
new_creds = "/root/.openclaw/credentials"
if os.path.exists(old_creds):
    shutil.copytree(old_creds, new_creds, dirs_exist_ok=True)
    print("Copied credentials")

# Copy skills
old_skills = "/root/.clawdbot/skills"
new_skills = "/root/.openclaw/skills"
if os.path.exists(old_skills):
    shutil.copytree(old_skills, new_skills, dirs_exist_ok=True)
    print("Copied skills")

# Copy memory
old_mem = "/root/.clawdbot/memory"
new_mem = "/root/.openclaw/memory"
if os.path.exists(old_mem):
    shutil.copytree(old_mem, new_mem, dirs_exist_ok=True)
    print("Copied memory")

# Copy telegram state
old_tg = "/root/.clawdbot/telegram"
new_tg = "/root/.openclaw/telegram"
if os.path.exists(old_tg):
    shutil.copytree(old_tg, new_tg, dirs_exist_ok=True)
    print("Copied telegram state")

# Copy devices
old_dev = "/root/.clawdbot/devices"
new_dev = "/root/.openclaw/devices"
if os.path.exists(old_dev):
    shutil.copytree(old_dev, new_dev, dirs_exist_ok=True)
    print("Copied devices")

print("MIGRATION COMPLETE: clawdbot -> openclaw")
