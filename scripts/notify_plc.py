#!/usr/bin/env python3
"""Send notification and write status file to PLC laptop"""
import requests
import json

PLC_LAPTOP = "http://100.72.2.99:8765"

# Send notification
try:
    r = requests.post(f"{PLC_LAPTOP}/notify", json={
        "title": "YOU ARE ONLINE!",
        "message": "Network working! VPS: 100.102.30.102 | Travel: 100.83.251.23 | Test: curl http://100.102.30.102:8200/health",
        "type": "toast"
    })
    print(f"Notification: {r.json()}")
except Exception as e:
    print(f"Notification failed: {e}")

# Write status file to desktop
status_content = """FACTORYLM NETWORK STATUS
========================
YOU ARE ONLINE AND CONNECTED!

Your Jarvis Node: http://100.72.2.99:8765 (WORKING)

Other Nodes:
- Travel Laptop: http://100.83.251.23:8765
- VPS Brain: 100.102.30.102 (SSH: root@100.102.30.102)
- Diagnosis Service: http://100.102.30.102:8200

TEST COMMANDS (run in PowerShell):
----------------------------------
curl http://localhost:8765/health
curl http://100.83.251.23:8765/health
curl http://100.102.30.102:8200/health
curl -X POST http://100.102.30.102:8200/diagnose -H "Content-Type: application/json" -d "{\\"question\\": \\"test\\"}"

The network IS working. Claude Code on Travel Laptop can reach you.
"""

try:
    r = requests.post(f"{PLC_LAPTOP}/files/write", json={
        "path": "C:/Users/hharp/Desktop/NETWORK_STATUS.txt",
        "content": status_content
    })
    print(f"Status file: {r.json()}")
except Exception as e:
    print(f"Status file failed: {e}")

# Also write network credentials
creds_content = """NETWORK CREDENTIALS
===================
VPS SSH: ssh root@100.102.30.102
Travel Laptop SSH: ssh hharp@100.83.251.23
PLC Laptop (you): 100.72.2.99

Jarvis Node endpoints:
- /health - Check status
- /shell - Run commands
- /files/read - Read files
- /files/write - Write files
- /notify - Send notifications
- /system-info - Get system info

Diagnosis Service (VPS port 8200):
- /health - Service health
- /network - All node status
- /diagnose - POST factory questions
"""

try:
    r = requests.post(f"{PLC_LAPTOP}/files/write", json={
        "path": "C:/Users/hharp/Desktop/NETWORK_CREDENTIALS.txt",
        "content": creds_content
    })
    print(f"Credentials file: {r.json()}")
except Exception as e:
    print(f"Credentials file failed: {e}")

print("\nDone! Check PLC laptop desktop for NETWORK_STATUS.txt")
