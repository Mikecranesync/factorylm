# FactoryLM Flagship Demo Script

**Duration:** 3-5 minutes
**Setup:** Micro820 PLC connected via Modbus TCP, Tony agent swarm active, Telegram open on screen.

---

## Pre-Demo Checklist

- [ ] PLC Laptop online (100.72.2.99), Jarvis Node running on :8765
- [ ] Micro820 PLC powered on (192.168.1.100:502)
- [ ] Gus bot (@FactoryLM_bot) active on Telegram
- [ ] Tony agent ready on Mac Mini (100.108.19.94)
- [ ] Matrix API accessible (http://100.72.2.99:8000)
- [ ] Split screen: terminal + Telegram

---

## Script

### 0:00-0:30 — Setup (30 sec)

**Mike:**
> "This is a real Allen-Bradley Micro820 PLC — the most common controller in small-to-mid manufacturing. It's running a simulated conveyor with a motor, temperature sensor, and pressure sensor. Connected over Modbus TCP, same as any factory floor."

**Show:** PLC hardware, wiring, blinking status LEDs.

### 0:30-1:30 — Trigger the Fault (60 sec)

**Mike:**
> "I'm going to simulate a motor stall — high current, motor stops. In a real factory, a tech would get paged, drive to the floor, open the manual, start guessing. That takes 30-90 minutes. Watch what happens instead."

**Action:** Write fault condition to PLC via Modbus TCP:
```
# Via jarvis-local
curl -X POST http://100.72.2.99:8765/api/modbus/write \
  -d '{"register": 40001, "value": 1}'  # Fault flag
```

**Show:** PLC fault LED illuminates.

### 1:30-2:30 — Agent Pipeline Fires (60 sec)

**Mike:**
> "The alarm monitor agent just detected the fault via Modbus. Watch the pipeline."

**Show on terminal** (narrate each step as it appears):

1. **Alarm Monitor:** "Fault detected — E001, motor stall, high current on conveyor 3"
2. **Triager:** "P2 priority, 4-hour SLA. 3 similar incidents in KB. Likely cause: bearing wear. Assigning Mike — best match for mechanical + electrical."
3. **WO Creator:** "Work order WO-2026-0223-001 created as GitHub Gist"
4. **Dispatcher:** "Notification sent to Mike via Telegram"

**Switch to Telegram:** Show the dispatch message arriving from Gus bot with full diagnosis, priority, and Gist link.

### 2:30-3:30 — The Intelligence Layer (60 sec)

**Mike:**
> "Three things just happened that no other system does:"
>
> "One — the triager searched past incidents and found this fault happened twice before. Both times it was bearing wear. That's episodic memory."
>
> "Two — the work order was created automatically in our CMMS with the diagnosis, parts list, and estimated repair time. Zero manual data entry."
>
> "Three — when I fix this and close the work order, the resolution gets recorded. After enough successful fixes, the system generates a playbook card. Eventually, that card becomes deterministic PLC code. The AI makes itself unnecessary."

**Show:** Open the Gist work order in browser — structured data, diagnosis, parts.

### 3:30-4:00 — Close the Loop (30 sec)

**Action:** Reply "COMPLETE" in Telegram. Show followup agent recording the episode.

**Mike:**
> "Total time from fault to dispatched technician with full diagnosis: under 60 seconds. Industry average: 30-90 minutes just for the page. And every fix makes the system smarter."

### 4:00-4:30 — The Pitch (30 sec)

**Mike:**
> "This is FactoryLM. Autonomous agents inside factory PLCs. $30 per device per month. We're deploying in 3 factories this quarter. The question isn't whether factories need this — it's how fast we can get it to them."

---

## Backup: If PLC Is Offline

If the physical PLC isn't available, demo using Matrix API mock data:
1. POST a mock incident to `/api/incidents`
2. Pipeline triggers the same way
3. All agent steps execute identically
4. Telegram notification still arrives

The demo works end-to-end regardless of PLC connectivity.

---

## Key Moments to Nail

| Moment | Why It Matters |
|--------|---------------|
| PLC fault LED lights up | Tangible — this is real hardware |
| Telegram notification arrives | Audience sees the end-to-end loop |
| "60 seconds vs 30-90 minutes" | Quantified value proposition |
| "The AI makes itself unnecessary" | Layer 0 vision — the big idea |
| Gist work order with full diagnosis | Shows production-ready infrastructure |
