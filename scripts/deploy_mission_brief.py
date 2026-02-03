"""
Deploy FACTORYLM MISSION BRIEF to all devices on the network.
"""
import requests
import json

MISSION_BRIEF = '''# FACTORYLM MISSION BRIEF

**ACTIVE PROJECT: Catapult Lakeland Demo**
**DEMO DATE: Tuesday, February 10th, 2026 @ 12:00-1:30 PM**
**COUNTDOWN: 8 days from Feb 2nd**

---

## YOUR ROLE (by device):
- **Travel Laptop (Miguelomaniac)**: Development, testing, presentation backup
- **PLC Laptop (LAPTOP-0KA3C70H)**: Factory I/O simulation, Micro 820 PLC connection, real hardware
- **VPS/Jarvis (100.68.120.99)**: Telegram gateway, diagnosis service, orchestration
- **Clawdbot**: Route factory questions to diagnosis service

---

## CRITICAL INFRASTRUCTURE

```
+-------------------------------------------------------------+
|                      YOUR NETWORK                           |
+-------------------------------------------------------------+
|  VPS (Jarvis)              Travel Laptop         PLC Laptop |
|  100.68.120.99             100.83.251.23         100.72.2.99|
|  +-------------+           +-------------+      +----------+|
|  | Clawdbot    |           | Jarvis Node |      |Jarvis    ||
|  | Telegram    |<--------->| Port 8765   |      |Node 8765 ||
|  | Gateway     |           | Claude Code |      |Factory IO||
|  +-------------+           +-------------+      |Micro 820 ||
|        ^                                         +----------+|
|        | Telegram                                            |
|   +----+----+                                               |
|   |  MIKE   |                                               |
|   | (Phone) |                                               |
|   +---------+                                               |
+-------------------------------------------------------------+
```

---

## KEY ENDPOINTS

| Device | URL | Purpose |
|--------|-----|---------|
| PLC Laptop | http://100.72.2.99:8765 | Factory I/O + Micro 820 PLC |
| Travel Laptop | http://100.83.251.23:8765 | Development + Presentation |
| VPS | 100.68.120.99 | Telegram bot (Jarvis/Clawdbot) |

---

## CURRENT SPRINT (DAY 1-2: Feb 2-3)

1. [x] Distribute mission brief to all devices
2. [ ] Create factorylm_diagnosis_service.py on VPS
3. [ ] Test end-to-end: Telegram -> VPS -> PLC Laptop -> Micro 820 -> LLM -> Response
4. [ ] Configure Jarvis to route "factory" questions to diagnosis service

---

## QUICK COMMANDS

```bash
# Check if laptops are online
curl http://100.72.2.99:8765/health
curl http://100.83.251.23:8765/health

# Execute command on PLC laptop
curl -X POST http://100.72.2.99:8765/shell \\
  -H "Content-Type: application/json" \\
  -d '{"command": "python --version", "timeout": 30}'

# Read file from PLC laptop
curl -X POST http://100.72.2.99:8765/files/read \\
  -H "Content-Type: application/json" \\
  -d '{"path": "C:/path/to/file"}'
```

---

## GITHUB REPOS

- Mikecranesync/factorylm - Main monorepo (THIS PROJECT)
- Mikecranesync/factorylm-landing - Marketing site (factorylm.com)
- Mikecranesync/factorylm-core - LLM library
- Mikecranesync/factorylm-plc-client - Hardware integration
- Mikecranesync/remoteme-jarvis-node - Remote control API

---

## IF YOU'RE CONFUSED

Read the full plan at: C:\\Users\\hharp\\.claude\\plans\\witty-noodling-plum.md

The mission: "Text your factory from your phone, AI tells you what's wrong."

Demo flow: Phone -> Telegram -> VPS -> PLC Laptop -> Micro 820 -> LLM -> Response

---

## DEMO NARRATIVE

"Factory technicians spend 40% of their time diagnosing problems. What if they could just ask their factory what's wrong?"

**The demo shows:**
1. Real PLC hardware responding to natural language questions
2. AI diagnosing machine issues in real-time
3. Multi-device orchestration (phone -> cloud -> factory floor)
'''

PLC_LAPTOP = "http://100.72.2.99:8765"
TRAVEL_LAPTOP = "http://100.83.251.23:8765"

def deploy_to_laptop(base_url, name):
    """Deploy mission brief to a laptop via Jarvis Node API."""
    print(f"\n{'='*50}")
    print(f"Deploying to {name} ({base_url})")
    print('='*50)

    # Check health first
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        health = r.json()
        print(f"Health: {health['status']} on {health['machine']}")
    except Exception as e:
        print(f"ERROR: Cannot reach {name}: {e}")
        return False

    # Create .claude directory
    print("Creating .claude directory...")
    r = requests.post(f"{base_url}/shell", json={
        "command": "if not exist C:\\Users\\hharp\\.claude mkdir C:\\Users\\hharp\\.claude",
        "timeout": 10
    })
    print(f"mkdir result: {r.json()}")

    # Write CLAUDE.md
    print("Writing CLAUDE.md...")
    r = requests.post(f"{base_url}/files/write", json={
        "path": "C:/Users/hharp/.claude/CLAUDE.md",
        "content": MISSION_BRIEF
    })
    print(f"write result: {r.json()}")

    # Verify
    print("Verifying...")
    r = requests.post(f"{base_url}/files/read", json={
        "path": "C:/Users/hharp/.claude/CLAUDE.md"
    })
    content = r.json().get("content", "")
    if "FACTORYLM MISSION BRIEF" in content:
        print(f"SUCCESS: Mission brief deployed to {name}")
        return True
    else:
        print(f"FAILED: Could not verify mission brief on {name}")
        return False

if __name__ == "__main__":
    print("FactoryLM Mission Brief Deployment")
    print("=" * 50)

    results = {}

    # Deploy to PLC laptop
    results["PLC Laptop"] = deploy_to_laptop(PLC_LAPTOP, "PLC Laptop")

    # Verify Travel laptop (current device - already done)
    print(f"\n{'='*50}")
    print("Travel Laptop (local)")
    print('='*50)
    try:
        with open("C:/Users/hharp/.claude/CLAUDE.md", "r") as f:
            content = f.read()
            if "FACTORYLM MISSION BRIEF" in content:
                print("SUCCESS: Mission brief present on Travel Laptop")
                results["Travel Laptop"] = True
            else:
                print("WARNING: CLAUDE.md exists but doesn't have mission brief")
                results["Travel Laptop"] = False
    except FileNotFoundError:
        print("ERROR: CLAUDE.md not found on Travel Laptop")
        results["Travel Laptop"] = False

    # Summary
    print(f"\n{'='*50}")
    print("DEPLOYMENT SUMMARY")
    print('='*50)
    for device, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {device}: {status}")

    all_ok = all(results.values())
    print(f"\nOverall: {'ALL DEVICES CONFIGURED' if all_ok else 'SOME DEVICES FAILED'}")
