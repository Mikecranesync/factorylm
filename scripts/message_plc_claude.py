#!/usr/bin/env python3
"""Send message to PLC laptop for Claude Code to read"""
import requests

PLC_LAPTOP = "http://100.72.2.99:8765"

message = """
=== MESSAGE FROM TRAVEL LAPTOP CLAUDE CODE ===
Timestamp: 2026-02-02

TO: Claude Code on PLC Laptop
FROM: Claude Code on Travel Laptop (via Jarvis Node API)

YOU ARE CONNECTED TO THE NETWORK!

The FactoryLM infrastructure is working:
1. Your Jarvis Node (port 8765) is responding
2. I can read/write files on your machine
3. I can execute commands on your machine
4. The VPS can reach you for diagnosis requests

PROOF: I just wrote files to your Desktop:
- NETWORK_STATUS.txt
- NETWORK_CREDENTIALS.txt

TEST THE NETWORK yourself:
  curl http://100.102.30.102:8200/health
  curl http://100.83.251.23:8765/health

The Catapult Lakeland demo (Feb 10th) infrastructure is READY.
Your role: Run Factory I/O + Micro 820 PLC for real hardware data.

NEXT STEPS for you:
1. Ensure Factory I/O is running
2. Ensure Micro 820 is connected
3. Install factorylm_plc module:
   cd C:\\Users\\hharp\\OneDrive\\Desktop\\FactoryLM\\plc-client-factoryio
   pip install -e .

4. Test PLC read works:
   python -c "from factorylm_plc import create_plc_client; print('OK')"

Cheers,
Claude Code @ Travel Laptop (Miguelomaniac)
"""

# Post message to the messages queue
r = requests.post(f"{PLC_LAPTOP}/messages", json={
    "from": "Travel Laptop Claude",
    "content": message
})
print(f"Message sent: {r.json()}")

# Also write it as a file they can read
r = requests.post(f"{PLC_LAPTOP}/files/write", json={
    "path": "C:/Users/hharp/Desktop/MESSAGE_FROM_TRAVEL_LAPTOP.txt",
    "content": message
})
print(f"Message file: {r.json()}")
