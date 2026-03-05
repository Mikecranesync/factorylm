# FactoryLM Vision: Multimodal AI Diagnostics for Industrial Automation

**NVIDIA Cosmos Cookoff — Competition Entry**
**Submission Deadline: March 5, 2026**
**Model Used: NVIDIA Cosmos Reason2-8B (via vLLM 0.15.1)**
**Last Updated: February 20, 2026**

---

## Executive Summary

Factory technicians spend an estimated 40% of their working time diagnosing equipment faults —
manually inspecting machinery, reading PLC screens, and cross-referencing error codes against paper
manuals. This time is expensive, slow, and error-prone. The consequences range from unplanned
downtime costing thousands of dollars per minute to workplace injuries that together burden
industry with over $170 billion annually in the United States alone.

FactoryLM Vision is a multimodal AI diagnostics system that attacks this problem directly. It
fuses live video from factory floor cameras with real-time PLC register data, feeds both into
NVIDIA's Cosmos Reason2-8B model, and surfaces a structured, actionable diagnosis to a factory
technician via a simple text interface — as fast as asking a question on their phone.

The system is built on real hardware: an Allen-Bradley Micro 820 PLC, a Factory I/O simulation
environment connected via live Modbus TCP, a Raspberry Pi edge device for on-premise data
collection, and a cloud AI layer served from a Vast.ai L40S GPU. The interface is a Telegram bot.
A technician on the floor can photograph a machine or describe a symptom, and within seconds
receive a diagnosis grounded in both what the AI sees and what the instruments report.

As of February 20, 2026, live end-to-end integration is complete and validated. The system
successfully read 19 live PLC tags from the Allen-Bradley Micro 820 over Modbus TCP, captured
the Factory I/O "From A to B" scene, and produced a structured diagnosis in 17.0 seconds —
cross-correlating visual observations (stationary box visible on conveyor) with PLC telemetry
(motor energized but speed register at zero) to identify a motor paradox that neither source
alone could surface.

This document describes the architecture, implementation, and validation results of FactoryLM
Vision as submitted to the NVIDIA Cosmos Cookoff.

---

## 1. Problem Statement

### 1.1 The Diagnostic Gap in Industrial Automation

Modern factory equipment is instrumented. PLCs record motor current, temperature, pressure,
conveyor speed, and dozens of boolean I/O states at scan rates of 10 Hz or faster. Cameras watch
production lines. Yet when something goes wrong, the diagnostic process remains largely manual:

- A fault alarm trips.
- A technician is paged.
- They walk to the machine, read the HMI display, pull up a fault log, and begin a checklist.
- They may call an OEM support line, wait on hold, and describe what they see verbally.

The problem is not a lack of data — it is a lack of inference. The PLC knows the motor current
spiked to 5.8A before the fault. The camera saw the conveyor belt stop moving. Nobody has
connected these observations into a coherent diagnosis automatically.

### 1.2 Why Existing Approaches Fall Short

Rule-based expert systems exist and catch obvious faults. If motor current exceeds a threshold, a
fault code fires. But they cannot:

- Correlate a visual observation ("the belt is bunched up on the left side") with an electrical
  anomaly (overcurrent) to diagnose the root cause (a misaligned roller).
- Distinguish between a genuine E-stop event and a stuck E-stop contact.
- Answer open-ended technician questions: "Is this safe to restart?"

Large language models know about industrial equipment in general but have no access to the live
sensor state of a specific machine. They hallucinate register values and cannot see the floor.

Vision-language models can watch video but, deployed alone, have no access to PLC telemetry.
They see motion but cannot read amperage, temperature, or pressure.

FactoryLM Vision bridges this gap by treating the problem as a grounded reasoning problem: give
the model both the visual stream and the instrument readings, and let it reason across both modalities.

### 1.3 The Scale of the Opportunity

- Unplanned industrial downtime costs manufacturers an average of $50,000 per hour (ARC Advisory
  Group, 2024).
- The global predictive maintenance market is projected to reach $28.2 billion by 2026 (MarketsAndMarkets).
- The US Bureau of Labor Statistics estimates $170+ billion annually in workplace injury costs,
  many of which occur during manual fault diagnosis and repair.

Even a 10% reduction in mean time to diagnose (MTTD) across a mid-size factory floor produces
measurable ROI within weeks of deployment.

---

## 2. Solution Architecture

### 2.1 System Overview

FactoryLM Vision is organized as a four-layer stack:

```
+------------------------------------------------------------------+
|                     TECHNICIAN INTERFACE                         |
|   Phone / Telegram Bot  →  "Is the conveyor jammed?"            |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                      CLOUD AI LAYER                              |
|   Vast.ai L40S GPU (100.68.120.99)                               |
|   ┌─────────────────────────────────────────────────────────┐   |
|   │  vLLM 0.15.1 serving nvidia/Cosmos-Reason2-8B           │   |
|   │  OpenAI-compatible endpoint: /v1/chat/completions        │   |
|   │  Context: 256K tokens | Chain-of-thought: <think> blocks│   |
|   └─────────────────────────────────────────────────────────┘   |
|   ┌─────────────────────────────────────────────────────────┐   |
|   │  diagnosis_engine.py                                     │   |
|   │  - Encodes video/image as base64                         │   |
|   │  - Injects PLC snapshot into structured prompt           │   |
|   │  - Runs rule-based pre-filter (8 fault codes)            │   |
|   │  - Parses <think> chain-of-thought from response         │   |
|   └─────────────────────────────────────────────────────────┘   |
+------------------------------------------------------------------+
                              |
                         Tailscale VPN
                              |
+---------------------------+ | +----------------------------------+
|    PLC LAPTOP              | | |    EDGE DEVICE (Raspberry Pi)    |
|    (100.72.2.99)           | | |                                  |
|  ┌────────────────────┐   | | |  ┌───────────────────────────┐  |
|  │  Factory I/O Sim   │   | | |  │  factorylm-edge/          │  |
|  │  "From A to B"     │   | | |  │  Modbus TCP Server        │  |
|  │  scene             │<──┤ ├─┤  │  GPIO bridge for PLC I/O  │  |
|  └────────────────────┘   │   │  └───────────────────────────┘  |
|  ┌────────────────────┐   │   │  ┌───────────────────────────┐  |
|  │  Allen-Bradley     │   │   │  │  edge_gateway.py          │  |
|  │  Micro 820 PLC     │<──┘   └─>│  Read holding regs 100-105│  |
|  │  Modbus TCP :502   │          │  Read coils 0-17           │  |
|  └────────────────────┘          └───────────────────────────┘  |
+---------------------------+   +----------------------------------+
                   |
          Modbus TCP (port 502)
                   |
+------------------------------------------------------------------+
|                   PHYSICAL HARDWARE LAYER                        |
|   Allen-Bradley Micro 820 PLC  (192.168.1.100)                   |
|   - 18 coils: Conveyor, Emitter, Sensors, E-stop, DI/DO         |
|   - Holding registers 100-105: speed, current, temp, pressure   |
|   - Factory I/O bridge coils 0-6: motor, fault, conveyor, sensor|
+------------------------------------------------------------------+
```

### 2.2 Data Flow for a Diagnostic Request

1. Technician sends a message to the Telegram bot: "The line stopped. What happened?"
2. Orchestrator (VPS) triggers a capture: `capture_fio.py` records a 15-second MP4 clip from
   the Factory I/O window at 4 FPS.
3. Simultaneously, `edge_gateway.py` reads the PLC: coils 0-17 and holding registers 100-105
   via Modbus TCP.
4. `diagnosis_engine.py` builds the multimodal prompt: video as base64 + PLC register snapshot
   formatted as structured text + fault pre-analysis from the rule engine.
5. The payload is POSTed to the vLLM endpoint serving Cosmos Reason2-8B.
6. Cosmos R2 returns a response with a `<think>` chain-of-thought block followed by the diagnosis.
7. The engine parses the response and returns structured output: reasoning, diagnosis, usage stats.
8. The Telegram bot delivers the diagnosis back to the technician's phone.

---

## 3. Technical Implementation

### 3.1 Video Capture: `cookoff/capture_fio.py`

The screen recorder uses the `mss` library for low-overhead multi-monitor capture. Frames are
captured at 4 FPS — matching the temporal density of Cosmos R2's training data — and assembled
into H.264-encoded MP4 files via `ffmpeg` with `libx264 / yuv420p` encoding, the format
expected by R2's vision encoder.

```
python cookoff/capture_fio.py record --duration 15 --label box_jam
```

Three operational modes are supported:
- `screenshot` — single PNG for static scene analysis
- `record` — timed MP4 clip for motion analysis
- `auto` — multi-scenario batch recording (operator advances through states manually)

Output files follow the naming convention `{label}_{timestamp}.mp4` and are stored in
`cookoff/clips/`.

### 3.2 PLC Integration

**Hardware:** Allen-Bradley Micro 820 PLC at `192.168.1.100:502`.

**Coil map (18 addresses):**

| Address | Variable | Direction | Description |
|---------|----------|-----------|-------------|
| 0 | Conveyor | PLC -> FIO | Belt motor command |
| 1 | Emitter | PLC -> FIO | Item spawner |
| 2 | SensorStart | FIO -> PLC | Entry photoeye |
| 3 | SensorEnd | FIO -> PLC | Exit photoeye |
| 4 | RunCommand | Remote | API/Telegram trigger |
| 7 | _IO_EM_DI_00 | Physical | 3-position switch CENTER |
| 8 | _IO_EM_DI_01 | Physical | E-stop NO contact |
| 9 | _IO_EM_DI_02 | Physical | E-stop NC contact |
| 15 | _IO_EM_DO_00 | Physical | Indicator LED |
| 16 | _IO_EM_DO_01 | Physical | E-stop LED |

**Holding registers:**

| Address | Tag | Scale | Description |
|---------|-----|-------|-------------|
| 100 | motor_speed | 1x | Speed 0-100% |
| 101 | motor_current | 0.1x | Amps (raw / 10) |
| 102 | temperature | 0.1x | Degrees C (raw / 10) |
| 103 | pressure | 1x | PSI |
| 104 | conveyor_speed | 1x | Belt speed 0-100% |
| 105 | error_code | 1x | 0=OK, 1=Overload, 2=Overheat, 3=Jam |

The `Micro820PLC` class in `services/plc-modbus/src/factorylm_plc/micro820.py` reads all coils
and registers in two bulk Modbus reads (minimizing round trips) and returns a typed `MachineState`
object. The `edge_gateway.py` integration wraps `ModbusTcpClient` for use from the VPS, traversing
the Tailscale mesh network to reach the PLC laptop.

### 3.3 Rule-Based Fault Pre-Filter: `diagnosis/conveyor_faults.py`

Before involving the LLM, the system runs a deterministic fault classifier over the PLC snapshot.
This serves two purposes: it catches obvious faults instantly (no LLM latency) and injects
structured fault evidence into the R2 prompt to guide its reasoning.

Eight fault rules are implemented across four severity levels:

| Code | Severity | Condition | Threshold |
|------|----------|-----------|-----------|
| E001 | EMERGENCY | E-stop active | `e_stop == True` |
| M001 | CRITICAL | Motor overcurrent | `motor_current > 5.0A` |
| T001 | CRITICAL | High temperature | `temperature > 80.0°C` |
| C001 | CRITICAL | Conveyor jam | Both sensors active + motor running |
| M002 | CRITICAL | Unexpected motor stop | Motor stopped, speed setpoint nonzero |
| P001 | WARNING | Low pneumatic pressure | `pressure < 60 PSI` |
| M003 | WARNING | Motor speed mismatch | `motor_speed < 30%` vs. `conveyor_speed > 50%` |
| T002 | WARNING | Elevated temperature | `65°C < temperature <= 80°C` |

Each detected fault produces a `FaultDiagnosis` dataclass containing the fault code, severity,
human-readable title, description, list of likely causes, and suggested maintenance checks.

The formatted output of this analysis is injected directly into the Cosmos R2 prompt. The model
is told: "Here is what the rule engine found. Now look at the video and tell me if the visual
evidence confirms or contradicts these findings."

### 3.4 Cosmos Reason2-8B Integration: `cookoff/diagnosis_engine.py`

**Model:** `nvidia/Cosmos-Reason2-8B`
**Serving:** vLLM 0.15.1 on Vast.ai L40S GPU, Virginia region ($0.53/hr spot pricing)
**Endpoint:** OpenAI-compatible `/v1/chat/completions`

**Sampling configuration (from NVIDIA R2 documentation):**
```python
temperature = 0.6
top_p       = 0.95
max_tokens  = 4096   # sufficient for full chain-of-thought reasoning
```

**Prompt architecture** (`cookoff/prompts/factory_diagnosis.yaml`):

The system prompt establishes the model's role as a factory diagnostics AI. It is instructed to
cross-reference visual observations with PLC telemetry and to flag discrepancies between the two
modalities as diagnostic signals in their own right. For example, if the solenoid register reads
ON but the camera shows no actuator motion, the model is expected to call out a likely wiring
fault or stuck actuator — information neither source alone could surface.

Three user prompt templates handle different query types:

- `user_diagnosis` — Full PLC snapshot + fault analysis + video. General diagnosis request.
- `user_question` — Same context, but answers a specific technician question.
- `user_describe` — Video only. Scene description without PLC context.

All prompts request the `<think>...</think>` chain-of-thought format followed by a plain-language
diagnosis. The engine parses these blocks and returns them separately, allowing the Telegram
interface to surface just the diagnosis while preserving the full reasoning for dashboard display.

**Media encoding:** Images and video are base64-encoded and submitted as OpenAI-format
`image_url` / `video_url` content blocks. Per R2 documentation, media is placed before text in
the user message content array.

### 3.5 Prompt Injection Example

For a simulated "jam" scenario, the prompt includes:

```
## Live PLC Register Data (Allen-Bradley Micro 820)
Digital I/O:
  conveyor_running: ON
  e_stop_active: OFF
  fault_alarm: ON
  motor_running: ON
  sensor_1_active: ON
  sensor_2_active: ON
Analog Registers:
  conveyor_speed: 50
  error_code: 3
  motor_current: 5.8
  motor_speed: 45
  pressure: 72
  temperature: 68.0

## Automated Fault Analysis
[CRITICAL] M001: Motor Overcurrent
Motor current (5.8A) exceeds safe limit (5.0A). Risk of thermal damage.
Likely Causes:
  - Mechanical binding or jam
  - Bearing failure
  - Belt tension too high
  - Overloaded conveyor
...

[CRITICAL] C001: Conveyor Jam Detected
Both part sensors are active simultaneously. Product flow is blocked.
...
```

This structured context lets Cosmos R2 reason about the physical world: the motor is fighting
harder than it should (5.8A vs. 2.3A nominal), both photoeyes are blocked, and error code 3
confirms a jam condition. The video feed provides spatial confirmation.

### 3.6 Raspberry Pi Edge Device

The `services/plc-modbus/factorylm-edge/` stack implements a Modbus TCP server on a Raspberry Pi
for on-premise PLC connectivity without a PC intermediate. GPIO pins are mapped to PLC I/O in
`gpio_mapping.py`. The edge server bridges Raspberry Pi GPIO to Modbus TCP register space,
allowing the VPS to poll physical hardware state through the standard Modbus protocol over the
Tailscale mesh.

This architecture enables deployment scenarios where the PLC laptop is not present: the Pi sits
on the DIN rail, reads PLC signals directly through its GPIO, and exposes them as a Modbus server
to the cloud AI layer.

---

## 4. Results and Validation

### 4.1 Live PLC Integration Test (February 20, 2026)

On February 20, 2026, the full end-to-end stack was validated against a live Allen-Bradley
Micro 820 PLC connected via Modbus TCP at 192.168.1.100:502, with Factory I/O "From A to B"
scene running and Cosmos Reason2-8B served via vLLM 0.15.1 on a Vast.ai L40S (Virginia,
$0.53/hr), accessed through an SSH tunnel on localhost:8000.

**Live PLC tag dump — 19 tags read successfully from the Micro 820:**

```
conveyor_running: True
e_stop_active:    False
e_stop_nc:        True
emitter_active:   True
error_code:       0
fault_alarm:      False
item_count:       0
motor_current:    0.0
motor_running:    True
motor_speed:      0
motor_stopped:    False
pressure:         0
pushbutton:       False
run_command:      True
sensor_1_active:  False
sensor_2_active:  False
switch_center:    True
switch_right:     False
temperature:      0.0
```

**Cosmos R2 diagnosis — 17.0 seconds, 693 tokens:**

R2 produced a structured diagnosis identifying four findings from this live telemetry snapshot:

1. **Motor Paradox** — `motor_running=ON` combined with `motor_speed=0`. R2 correctly
   identified this as a potential mechanical failure or encoder/sensor error, noting that
   holding registers 101-105 are not mapped in the current scene configuration and flagging
   this as a likely source of the zero readings.
2. **Pneumatic Pressure Failure** — `pressure=0 PSI` flagged as critically low. R2 recommended
   checking the air supply, checking for leaks, and verifying the pressure transducer wiring
   before any restart.
3. **Inactive Sensors** — Both photoeyes reading OFF while a box was visible on the conveyor
   in the Factory I/O image. R2 flagged this as possible sensor misalignment or obscuration.
4. **Cross-modal reasoning** — R2 correlated the visual observation (stationary box visible on
   belt, orange motor visible and energized) with the PLC telemetry (motor commanded ON, speed
   reading zero, no sensor pulses) to conclude the system was energized but producing no
   mechanical output — a diagnosis impossible from either source alone.

This is the first validated demonstration of Cosmos R2 performing real-time factory diagnostics
by fusing live video from a factory simulation with live register data from a physical industrial
controller.

### 4.2 Full Scenario Test Matrix

All five fault scenarios were tested with real Factory I/O screenshots (not proxy images).
The following table records the actual measured latency and token counts from the test session
of February 20, 2026:

| Scenario | Latency | Tokens | Key Finding |
|----------|---------|--------|-------------|
| `normal` | 6.1s | 229 | "No anomalies detected. System functioning as designed." |
| `jam` | 19.2s | 678 | Identified overcurrent 5.8A, box/hopper causing blockages |
| `estop` | 14.4s | 601 | "E-stop engaged, not a hardware issue. Reset to resume." |
| `overheat` | 15.2s | 636 | "CRITICAL: 85°C exceeds limit. Check cooling." |
| `live PLC` | 17.0s | 693 | Motor paradox, pressure failure, cross-modal reasoning |

The `normal` scenario at 6.1s / 229 tokens demonstrates that the system is efficient when there
is nothing wrong: R2 exits its reasoning chain early rather than manufacturing spurious findings.
Latency scales with diagnostic complexity, which is the correct behavior for a safety-critical
system.

### 4.3 Question-Answering Mode

The diagnosis engine supports open-ended technician questions against the live PLC context and
image. Two questions were tested in the February 20 session:

- **"Is the conveyor running and why is the motor drawing so much current?"**
  Response: 10.2 seconds, 423 tokens. R2 correctly answered with PLC register evidence and cited
  specific tag values to support its conclusion.

- **"What equipment do you see?"**
  Response: 4.5 seconds. R2 correctly identified a roller conveyor, a box, and photoeye sensors
  from the Factory I/O screenshot.

### 4.4 Initial Integration Test (Reference)

In the first integration test (pre-live-hardware), a terminal screenshot was submitted as a
proxy image paired with the simulated "jam" PLC scenario. Despite the image being explicitly
not a factory environment, R2:

- Identified the three critical fault conditions from the PLC data: motor overcurrent (5.8A),
  Error Code 3 (jam), and elevated temperature (68°C approaching the 80°C alarm threshold).
- Flagged that the submitted image appeared to be a terminal window rather than factory
  equipment and noted this as a data quality discrepancy — demonstrating active cross-modal
  self-correction rather than passive acceptance of either source.
- Produced structured output with CRITICAL, WARNING, and RECOMMENDED ACTION sections including
  explicit safety guidance.

**Performance (initial test):** 25.8 seconds end-to-end, 784 tokens, L40S at $0.50/hr.

The improvement from 25.8s (initial, proxy image) to 6.1-19.2s (live, real Factory I/O
screenshots) reflects both prompt refinement and the model's ability to reason more efficiently
from genuine visual context.

---

## 5. Why Cosmos Reason2-8B

### 5.1 Physical World Understanding

Cosmos R2 is trained on world simulation data, giving it grounded intuitions about physical
causality. When it sees a conveyor belt and reads that current has doubled, it reasons about
mechanical load — not just pattern-matching on tokens. This is qualitatively different from a
general-purpose VLM that happens to know industrial terminology.

### 5.2 Chain-of-Thought Reasoning for Safety-Critical Decisions

Industrial diagnostics must be auditable. A technician restarting a motor after a jam needs to
know not just what the AI concluded but why. Cosmos R2's `<think>` blocks provide exactly this:
a structured reasoning trace that an expert can review before acting.

Example structure of a Cosmos R2 response:

```
<think>
The PLC data shows motor_current at 5.8A, which is 16% above the 5.0A
threshold. This is consistent with mechanical binding. Error Code 3
explicitly indicates a jam condition. Both sensor_1 and sensor_2 are
active simultaneously — in normal operation at most one photoeye should
be blocked at any given time, so this confirms product is wedged between
both detection points. The elevated temperature (68°C) is secondary to
the overcurrent event, likely resulting from the motor working against
a load for an extended period.

The video feed should show the belt stopped or moving slowly with
product accumulation visible...
</think>

DIAGNOSIS — CRITICAL

Primary fault: Conveyor jam with motor overcurrent
...
```

### 5.3 256K Token Context Window

Industrial prompts are verbose. A full shift of PLC register history, maintenance logs, and
operator notes can easily exceed 32K tokens. R2's 256K context window enables diagnostics that
incorporate historical trend data — "the current has been climbing over the last two hours" —
alongside real-time sensor snapshots.

### 5.4 Video-Native Architecture

R2 accepts video natively as a first-class modality. Submitted as an MP4 at 4 FPS, it can
observe temporal patterns invisible to still image analysis: a belt that starts moving then
decelerates over 10 seconds (indicating a developing jam rather than a sudden blockage), or an
actuator that cycles intermittently (indicating an electrical fault vs. a mechanical one).

---

## 6. Roadmap

### 6.1 Phase 3: Live PLC Integration — COMPLETE (February 20, 2026)

Live Modbus TCP reads from the Allen-Bradley Micro 820 are integrated into the diagnostic
pipeline. The system successfully read 19 PLC tags per request and passed them to the
`diagnosis_engine.py` orchestrator alongside real Factory I/O screenshots. Cosmos R2 produced
structured cross-modal diagnoses in 17.0 seconds on the first live run. See Section 4.1 for
detailed results.

### 6.2 Phase 4: Telegram Integration — COMPLETE

The Telegram bot (Clawdbot, running on VPS 100.68.120.99) is operational and routing factory
diagnostic requests to the diagnosis engine. Technicians can send a photo or question and
receive a Cosmos R2 diagnosis in return. The Telegram adapter handles media download, passes
media and PLC snapshot to `diagnosis_engine.py`, and returns the diagnosis text.

### 6.3 Phase 5: Real-Time Dashboard

A web dashboard displaying three panels simultaneously:
- Live Factory I/O camera feed
- PLC register state (color-coded by fault threshold)
- Cosmos R2 diagnosis with chain-of-thought reasoning

This dashboard provides the demo narrative in a single view: the technician's question, the AI's
visual and sensor evidence, and the structured diagnosis.

### 6.4 Phase 6: Submission Package

- Public GitHub repository with complete source, setup instructions, and reproducible cookbook recipes
- Demo video showing the end-to-end flow from Telegram message to PLC read to Cosmos R2 diagnosis
- Supplementary notebook with annotated examples of R2's cross-modal reasoning

### 6.5 Longer-Term: Knowledge Distillation (Layer 0)

The FactoryLM architecture is designed to convert Layer 3 intelligence (Cosmos R2 cloud inference)
into Layer 0 deterministic code over time. Each Cosmos R2 diagnosis that is confirmed by a
technician as correct becomes a training example. Over weeks, the rule engine in
`diagnosis/conveyor_faults.py` grows richer, and the system progressively requires less cloud AI
intervention for common fault patterns — reducing both cost and latency.

---

## 7. Reproducibility

All components are open-source and standard-protocol:

| Component | Implementation | Protocol |
|-----------|---------------|----------|
| PLC communication | pymodbus 3.11 | Modbus TCP (port 502) |
| Video capture | mss + ffmpeg | H.264/MP4 at 4 FPS |
| AI inference | vLLM 0.15.1 | OpenAI `/v1/chat/completions` |
| Network mesh | Tailscale | WireGuard VPN |
| User interface | python-telegram-bot | Telegram Bot API |
| Simulation | Factory I/O | Modbus TCP driver |

The system requires no proprietary protocols, no PLC vendor SDKs, and no specialized hardware
beyond a standard industrial PLC with Modbus TCP support. Any Allen-Bradley, Siemens, or
Automation Direct PLC with a Modbus TCP server can be substituted without code changes — only
the register map in `config/factoryio.yaml` needs updating.

GPU inference is served via vLLM on commodity Vast.ai spot instances. The full stack runs for
approximately $0.53/hr in cloud GPU costs during active use (L40S, Virginia region, validated
February 20, 2026).

---

## 8. References

1. NVIDIA Cosmos Reason2-8B model documentation and sampling recommendations.
   https://huggingface.co/nvidia/Cosmos-Reason2-8B

2. vLLM Project — High-throughput and memory-efficient inference engine.
   https://github.com/vllm-project/vllm

3. ARC Advisory Group, "The Cost of Unplanned Downtime in Manufacturing," 2024.

4. MarketsAndMarkets, "Predictive Maintenance Market — Global Forecast to 2026," 2024.

5. U.S. Bureau of Labor Statistics, "Employer Costs for Employee Compensation," 2024.
   https://www.bls.gov/news.release/ecec.nr0.htm

6. Modbus Organization, "Modbus Application Protocol Specification V1.1b3," 2012.
   https://modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf

7. Allen-Bradley Micro 820 Programmable Logic Controller User Manual, 2022.
   Rockwell Automation Publication 2080-UM002.

8. Factory I/O — 3D Factory Simulation. Real Games, Lda.
   https://factoryio.com

---

## Appendix A: File Reference

| File | Purpose |
|------|---------|
| `cookoff/capture_fio.py` | Screen recorder — 4 FPS MP4 capture from Factory I/O |
| `cookoff/diagnosis_engine.py` | Orchestrator — builds multimodal prompt, calls R2, parses response |
| `cookoff/prompts/factory_diagnosis.yaml` | Structured prompt templates (system + 3 user variants) |
| `diagnosis/conveyor_faults.py` | Rule-based fault classifier — 8 fault codes, 4 severity levels |
| `services/plc-modbus/src/factorylm_plc/micro820.py` | Allen-Bradley Micro 820 Modbus client |
| `integrations/edge_gateway.py` | Cloud-to-edge Modbus polling via Tailscale |
| `services/plc-modbus/factorylm-edge/edge_server.py` | Raspberry Pi Modbus TCP server |
| `config/factoryio.yaml` | Coil and register map for "From A to B" scene |

---

## Appendix B: Quick Start

```bash
# Install dependencies
pip install requests pyyaml pymodbus mss

# Capture a Factory I/O screenshot
python cookoff/capture_fio.py screenshot --label baseline

# Run diagnosis with simulated jam data (no PLC required)
VLLM_URL=http://<your-vllm-host>:8000/v1/chat/completions \
    python cookoff/diagnosis_engine.py \
    --image cookoff/clips/baseline_*.png \
    --simulate-plc jam

# Ask a specific question
python cookoff/diagnosis_engine.py \
    --image cookoff/clips/baseline_*.png \
    --simulate-plc estop \
    --question "Is it safe to restart the conveyor?"

# Output as JSON for downstream processing
python cookoff/diagnosis_engine.py \
    --image cookoff/clips/baseline_*.png \
    --simulate-plc overheat \
    --json

# Run diagnosis against a LIVE PLC (Micro 820 at 192.168.1.100:502)
VLLM_URL=http://localhost:8000/v1/chat/completions \
    python cookoff/diagnosis_engine.py \
    --image cookoff/clips/baseline_*.png \
    --plc-host 192.168.1.100 \
    --plc-port 502

# Ask a specific question against live PLC data
VLLM_URL=http://localhost:8000/v1/chat/completions \
    python cookoff/diagnosis_engine.py \
    --image cookoff/clips/baseline_*.png \
    --plc-host 192.168.1.100 \
    --question "Is the conveyor running and why is the motor drawing so much current?"
```

---

*FactoryLM Vision — NVIDIA Cosmos Cookoff Entry*
*Repository: https://github.com/Mikecranesync/factorylm*
*Contact: Mikecranesync*
*Date: February 2026 | Last updated: February 20, 2026 — live PLC integration validated*
