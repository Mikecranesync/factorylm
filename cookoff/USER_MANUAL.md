# FactoryLM Vision — Cosmos R2 Diagnosis System
## User Manual

**System:** FactoryLM Vision — Multimodal Factory Diagnostics
**Model:** NVIDIA Cosmos Reason2-8B
**Competition:** NVIDIA Cosmos Cookoff (Submission Deadline: March 5, 2026)
**Version:** February 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Prerequisites](#2-prerequisites)
3. [Quick Start (Step by Step)](#3-quick-start-step-by-step)
4. [Command Reference](#4-command-reference)
5. [PLC Configuration](#5-plc-configuration)
6. [Simulated PLC Scenarios](#6-simulated-plc-scenarios)
7. [Fault Detection Reference](#7-fault-detection-reference)
8. [Prompt Architecture](#8-prompt-architecture)
9. [Architecture Overview](#9-architecture-overview)
10. [Cost Management](#10-cost-management)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. System Overview

### 1.1 What FactoryLM Vision Does

FactoryLM Vision is a multimodal factory diagnostics system built for the NVIDIA Cosmos Cookoff competition. It fuses two data streams that have historically been analyzed in isolation:

- **Visual data:** Live screenshots or video recordings of the Factory I/O simulation environment (or real factory cameras), captured at 4 FPS
- **PLC telemetry:** Real-time register reads from an Allen-Bradley Micro 820 PLC via Modbus TCP — coil states (digital I/O) and holding registers (speed, current, temperature, pressure, error codes)

Both streams are injected into a structured prompt and submitted to **NVIDIA Cosmos Reason2-8B** (served via vLLM on a Vast.ai L40S GPU). The model reasons across both modalities simultaneously and returns a chain-of-thought diagnosis that a factory technician can act on immediately.

### 1.2 The Diagnostic Problem

Modern factory equipment generates enormous volumes of sensor data, but diagnosis remains largely manual. When a fault trips, a technician must physically walk to the machine, read the HMI, cross-reference the fault log against paper manuals, and then form a diagnosis — often without seeing the camera feed and the PLC registers side by side.

The key insight FactoryLM Vision exploits: when video and PLC data *disagree*, that discrepancy is itself diagnostic information. If the conveyor motor register reads ON but the camera shows the belt has stopped, you have a broken drive chain or wiring fault. A rule engine alone cannot make that inference. A vision model without PLC access cannot make it either. Only a model with both can.

### 1.3 Why Cosmos Reason2-8B

Cosmos R2 was chosen for three specific capabilities:

1. **Physical world grounding.** Cosmos R2 is trained on world simulation data, giving it genuine intuitions about mechanical causality — not just industrial terminology pattern-matching. When it sees a conveyor and reads that motor current has doubled, it reasons about mechanical load.

2. **Chain-of-thought reasoning for safety-critical decisions.** The `<think>...</think>` blocks provide an auditable reasoning trace. A technician can read the model's reasoning before restarting a motor after a jam — essential in industrial settings where wrong decisions have physical consequences.

3. **256K token context window.** Industrial diagnostic prompts are verbose. Full shift histories, maintenance logs, and operator notes can easily exceed 32K tokens. R2's large context enables diagnostics incorporating historical trend data alongside real-time snapshots.

4. **Native video input.** R2 accepts MP4 video as a first-class modality at the same API endpoint as images. This enables temporal pattern analysis: a belt that decelerates over 10 seconds (developing jam) versus one that stops instantly (sudden blockage) — information invisible to a single frame.

### 1.4 The Four-Layer Stack

The system is organized as a four-layer architecture where intelligence flows downward over time:

| Layer | Component | Description |
|-------|-----------|-------------|
| Layer 3 | Cosmos R2 (cloud) | NVIDIA Cosmos Reason2-8B on Vast.ai L40S GPU |
| Layer 2 | Fault pre-filter | Rule-based classifier in `diagnosis/conveyor_faults.py` — 8 fault codes, instant response |
| Layer 1 | Edge device | Raspberry Pi running `factorylm-edge/` — on-premise Modbus bridge |
| Layer 0 | Deterministic code + KB | Target state: confirmed diagnoses converted to rules, zero cloud dependency |

Over time, Cosmos R2 diagnoses confirmed by technicians become Layer 0 rules, progressively reducing cloud cost and latency.

---

## 2. Prerequisites

### 2.1 Python Environment

**Python 3.14+** is required. Install all dependencies with:

```bash
pip install requests pyyaml mss pymodbus pyautogui
```

| Package | Purpose |
|---------|---------|
| `requests` | HTTP calls to the vLLM endpoint |
| `pyyaml` | Loading prompt templates from `factory_diagnosis.yaml` |
| `mss` | Multi-monitor screen capture for Factory I/O |
| `pymodbus` | Modbus TCP client for PLC communication (3.11+) |
| `pyautogui` | (Optional) Window focus automation |

Additionally, **ffmpeg** must be in your PATH for video recording (MP4 assembly from frames). Download from https://ffmpeg.org/download.html and add to system PATH.

### 2.2 Vast.ai GPU Account

- Account at https://vast.ai with **$66 credit** remaining
- Target GPU: **L40S** at approximately **$0.50/hr** spot pricing
- SSH key configured in your Vast.ai account: the key at `~/.ssh/id_ed25519` must be added to your Vast.ai account SSH keys page before instances can be created

### 2.3 HuggingFace Token

The Cosmos Reason2-8B model requires a HuggingFace account with model access accepted.

- **Doppler project:** `openclaw/dev`
- **Doppler key:** `HF_TOKEN`
- Retrieve with: `doppler run --project openclaw --config dev -- printenv HF_TOKEN`
- Or set manually: `export HF_TOKEN=hf_...`

Accept the model license at: https://huggingface.co/nvidia/Cosmos-Reason2-8B

### 2.4 vastai CLI

The Vast.ai CLI is installed at:

```
C:/Users/hharp/AppData/Local/Python/pythoncore-3.14-64/Scripts/vastai.exe
```

For convenience, add this path to your system PATH or use the full path in all commands shown below.

### 2.5 Factory I/O

- **Factory I/O Ultimate Edition** installed and licensed
- Scene loaded: **"From A to B"** (File -> Open Scene -> From A to B)
- Modbus TCP driver configured in Factory I/O:
  1. File -> Drivers
  2. Select "Modbus TCP/IP Server"
  3. Click "Configuration" and verify coil addresses match the map in Section 5
  4. Click "Connect"

### 2.6 Allen-Bradley Micro 820 PLC (for live PLC mode)

- PLC IP: `192.168.1.100`, Modbus TCP port `502`
- Your PC IP must be in the `192.168.1.x/24` subnet (e.g., `192.168.1.50`)
- **Ethernet cable required** — Modbus TCP does not run over Wi-Fi on this hardware
- PLC programmed with the "From A to B" Structured Text program in `services/plc-modbus/scenes/`

For simulation-only use (no live hardware), the Ethernet cable and PLC are not required. The `--simulate-plc` flag provides full PLC data without any hardware.

---

## 3. Quick Start (Step by Step)

### Step 1: Spin Up a Vast.ai GPU Instance

Search for available L40S instances, cheapest first:

```bash
"C:/Users/hharp/AppData/Local/Python/pythoncore-3.14-64/Scripts/vastai.exe" search offers 'gpu_name=L40S num_gpus=1 reliability>0.95 inet_down>200 disk_space>50' --order 'dph_total' --limit 5
```

Review the output. Note the `ID` of the cheapest suitable offer. Create an instance from that offer:

```bash
"C:/Users/hharp/AppData/Local/Python/pythoncore-3.14-64/Scripts/vastai.exe" create instance <OFFER_ID> --image pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel --disk 80 --direct
```

Wait for the instance to reach `running` state. This typically takes 2-4 minutes:

```bash
"C:/Users/hharp/AppData/Local/Python/pythoncore-3.14-64/Scripts/vastai.exe" show instances
```

The output shows `SSH_HOST`, `PORT`, and `INSTANCE_ID`. Note all three — you will need them throughout the session.

### Step 2: Install vLLM and Start the Model Server

SSH into the instance:

```bash
ssh -i ~/.ssh/id_ed25519 -p <PORT> root@<SSH_HOST>
```

Inside the instance, install dependencies and authenticate with HuggingFace:

```bash
pip install vllm huggingface_hub
huggingface-cli login --token <HF_TOKEN>
```

Start the vLLM server in the background. This command configures R2 with the recommended sampling parameters and `qwen3` reasoning parser for `<think>` block support:

```bash
nohup vllm serve nvidia/Cosmos-Reason2-8B \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.9 \
    --reasoning-parser qwen3 \
    > /tmp/vllm.log 2>&1 &
```

Monitor startup. Wait until you see `"Application startup complete"` before proceeding:

```bash
tail -f /tmp/vllm.log
```

Model download and initialization typically takes 5-10 minutes on first run. Subsequent starts on the same instance (if you did not destroy it) take under 2 minutes.

Press `Ctrl+C` to stop following the log. Exit the SSH session:

```bash
exit
```

### Step 3: Create an SSH Tunnel

The vLLM server on the Vast.ai instance is not publicly exposed. You access it through an SSH tunnel that forwards `localhost:8000` on your local machine to port 8000 on the instance:

```bash
ssh -i ~/.ssh/id_ed25519 -p <PORT> -f -N -L 8000:localhost:8000 root@<SSH_HOST>
```

Flag explanation:
- `-f` — Fork into background after authentication
- `-N` — Do not execute a remote command (tunnel only)
- `-L 8000:localhost:8000` — Forward local port 8000 to remote port 8000

Verify the tunnel is working:

```bash
curl http://localhost:8000/health
```

Expected response: `{"status":"ok"}` or similar. If you get `Connection refused`, the tunnel or the vLLM server is not yet ready.

### Step 4: Capture Factory I/O

Make sure Factory I/O is running with the "From A to B" scene visible on your screen.

**Take a single screenshot:**

```bash
python cookoff/capture_fio.py screenshot --label my_test
```

Output is saved to `cookoff/clips/my_test_<timestamp>.png`.

**Record a 15-second video clip at 4 FPS:**

```bash
python cookoff/capture_fio.py record --duration 15 --label normal_run
```

Output is saved to `cookoff/clips/normal_run_<timestamp>.mp4`.

**Record multiple scenarios in sequence (interactive):**

```bash
python cookoff/capture_fio.py auto --scenarios normal,jam,stop --duration 20
```

The tool will prompt you to set up each scenario in Factory I/O and press Enter before each recording starts.

All output files are stored in `cookoff/clips/`.

### Step 5: Run a Diagnosis

**Diagnose with simulated PLC data (no hardware required):**

```bash
python cookoff/diagnosis_engine.py --image cookoff/clips/my_test_*.png --simulate-plc jam
```

This uses the built-in "jam" scenario (see Section 6) as PLC data, sends the image to Cosmos R2, and prints the chain-of-thought reasoning and diagnosis.

**Diagnose with live Micro 820 PLC (Ethernet cable must be connected):**

```bash
python cookoff/diagnosis_engine.py --image cookoff/clips/my_test_*.png --live-plc
```

The engine reads coils 0-17 and holding registers 100-105 from the PLC at `192.168.1.100:502` and injects the live snapshot into the prompt.

**Ask a specific question:**

```bash
python cookoff/diagnosis_engine.py --image cookoff/clips/my_test_*.png --live-plc --question "Is the conveyor running?"
```

**Use a video clip instead of a still image:**

```bash
python cookoff/diagnosis_engine.py --video cookoff/clips/normal_run_*.mp4 --simulate-plc normal
```

**Output as JSON for programmatic use:**

```bash
python cookoff/diagnosis_engine.py --image cookoff/clips/my_test_*.png --simulate-plc normal --json
```

JSON output includes `reasoning`, `diagnosis`, `raw_response`, `usage` (token counts), and `elapsed_s`.

**Expected output (human-readable mode):**

```
FactoryLM Vision — Cosmos R2 Diagnosis Engine
============================================================
Media: cookoff/clips/my_test_20260220_143012.png
PLC: simulated:jam
Question: general diagnosis
Endpoint: http://localhost:8000/v1/chat/completions
============================================================

REASONING (chain-of-thought):
----------------------------------------
The PLC data shows motor_current at 5.8A, which is 16% above the 5.0A
threshold. This is consistent with mechanical binding. Error Code 3
explicitly indicates a jam condition...

DIAGNOSIS:
----------------------------------------
CRITICAL — Conveyor Jam with Motor Overcurrent

Primary fault: Both photoeyes blocked simultaneously (sensor_1: ON,
sensor_2: ON) with motor current elevated to 5.8A. Error Code 3 confirms
a jam condition...

[25.8s | 784 tokens]
```

### Step 6: Destroy the Vast.ai Instance

**Do this when you are done for the session.** Forgetting to destroy an instance costs money.

```bash
"C:/Users/hharp/AppData/Local/Python/pythoncore-3.14-64/Scripts/vastai.exe" destroy instance <INSTANCE_ID>
```

Verify it is gone:

```bash
"C:/Users/hharp/AppData/Local/Python/pythoncore-3.14-64/Scripts/vastai.exe" show instances
```

---

## 4. Command Reference

### 4.1 capture_fio.py

Located at `cookoff/capture_fio.py`. All output goes to `cookoff/clips/`.

**Subcommand: screenshot**

```
python cookoff/capture_fio.py screenshot [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--label` | `screenshot` | Label prefix for the output filename |
| `--monitor` | `1` | Monitor index. `1` = primary display. Use `2` for a secondary monitor if Factory I/O is on monitor 2. |

Output filename format: `{label}_{YYYYMMDD_HHMMSS}.png`

**Subcommand: record**

```
python cookoff/capture_fio.py record [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--duration` | `15.0` | Recording duration in seconds |
| `--label` | `clip` | Label prefix for the output filename |
| `--fps` | `4` | Frames per second. 4 FPS matches Cosmos R2 training data; do not increase without a reason. |
| `--monitor` | `1` | Monitor index |

Output filename format: `{label}_{YYYYMMDD_HHMMSS}.mp4`

The recorder captures frames as individual PNGs at the target FPS, then assembles them into an H.264 MP4 using ffmpeg (`libx264 / yuv420p`). If ffmpeg is not found, the raw frame directory is preserved as a fallback.

**Subcommand: auto**

```
python cookoff/capture_fio.py auto [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--scenarios` | `normal,box_jam,conveyor_stop` | Comma-separated list of scenario labels |
| `--duration` | `20.0` | Duration per scenario in seconds |

The `auto` subcommand iterates through each scenario label, prompts you to configure the Factory I/O scene, then records. This is useful for building a labeled dataset of fault scenarios in a single session.

### 4.2 diagnosis_engine.py

Located at `cookoff/diagnosis_engine.py`.

```
python cookoff/diagnosis_engine.py --image <path> | --video <path> [options]
```

**Media input (mutually exclusive, one required):**

| Flag | Description |
|------|-------------|
| `--image <path>` | Path to a PNG or JPG screenshot |
| `--video <path>` | Path to an MP4, AVI, or WebM clip |

**PLC data source (choose one or none):**

| Flag | Description |
|------|-------------|
| `--simulate-plc <scenario>` | Use a built-in simulated scenario. Values: `normal`, `jam`, `estop`, `idle`, `overheat` |
| `--live-plc` | Read live PLC registers via Modbus TCP at `--plc-host` |
| `--plc-json <path>` | Load PLC snapshot from a JSON file previously saved |

If no PLC source is specified, the engine runs in video-only mode and uses the `user_describe` prompt (scene description only, no register context).

**Live PLC options (used with `--live-plc`):**

| Flag | Default | Description |
|------|---------|-------------|
| `--plc-host` | `192.168.1.100` | PLC IP address |
| `--plc-port` | `502` | Modbus TCP port |

**Query options:**

| Flag | Description |
|------|-------------|
| `--question "<text>"` | Ask a specific question instead of requesting a general diagnosis. Activates the `user_question` prompt template. |

**Output and inference options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--url <url>` | `http://localhost:8000/v1/chat/completions` | vLLM endpoint URL. Can also be set via the `VLLM_URL` environment variable. |
| `--max-tokens <n>` | `4096` | Maximum tokens in the model response. 4096 is sufficient for full chain-of-thought. Increase to 8192 for very detailed analyses. |
| `--json` | Off | Output the full result as a JSON object instead of human-readable text. |

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `VLLM_URL` | Override the default vLLM endpoint URL. Equivalent to `--url`. |

---

## 5. PLC Configuration

### 5.1 Hardware

- **PLC Model:** Allen-Bradley Micro 820 (Firmware v12)
- **PLC IP:** `192.168.1.100`
- **PC IP:** `192.168.1.50` (subnet mask `255.255.255.0`)
- **Protocol:** Modbus TCP on port `502`
- **OPC UA:** Port `4840` (disabled by default; enable in Connected Components Workbench if needed)

### 5.2 Coil Map (Addresses 0-17)

The diagnosis engine reads all 18 coils in a single Modbus bulk read. Addresses are 0-based (pymodbus convention).

**"From A to B" Scene Coils (PLC to Factory I/O and back):**

| Address | Tag Name | Direction | Description |
|---------|----------|-----------|-------------|
| 0 | Conveyor | PLC -> FIO | Belt motor command — write TRUE to run conveyor |
| 1 | Emitter | PLC -> FIO | Item spawner — write TRUE to spawn boxes |
| 2 | SensorStart | FIO -> PLC | Entry photoeye — TRUE when a box is at the start |
| 3 | SensorEnd | FIO -> PLC | Exit photoeye — TRUE when a box reaches the end |
| 4 | RunCommand | Remote | API/Telegram trigger — write TRUE to start remotely |
| 5-6 | (unused) | — | Available for custom PLC variables |

**Physical I/O Panel Coils:**

| Address | Tag Name | Direction | Description |
|---------|----------|-----------|-------------|
| 7 | _IO_EM_DI_00 | Input | 3-position switch CENTER detect |
| 8 | _IO_EM_DI_01 | Input | E-stop NO contact (TRUE when E-stop is pressed) |
| 9 | _IO_EM_DI_02 | Input | E-stop NC contact (TRUE when E-stop is RELEASED — normal state) |
| 10 | _IO_EM_DI_03 | Input | 3-position switch RIGHT detect |
| 11 | _IO_EM_DI_04 | Input | Left momentary pushbutton |
| 12-14 | _IO_EM_DI_05-07 | Input | Unused digital inputs |
| 15 | _IO_EM_DO_00 | Output | 3-position switch indicator LED |
| 16 | _IO_EM_DO_01 | Output | E-stop indicator LED |
| 17 | _IO_EM_DO_03 | Output | Auxiliary output |

**3-Position Switch Logic:**

| Switch Position | DI_00 (addr 7) | DI_03 (addr 10) | DO_00 (addr 15) |
|-----------------|----------------|-----------------|-----------------|
| LEFT | OFF | OFF | OFF |
| CENTER | ON | OFF | ON |
| RIGHT | ON | ON | ON |

**E-Stop Logic:**

| E-Stop State | DI_01 (addr 8) | DI_02 (addr 9) | DO_01 (addr 16) |
|--------------|----------------|----------------|-----------------|
| Released (normal) | OFF | ON | OFF |
| Pressed (fault) | ON | OFF | ON |

Note: The diagnosis engine derives `fault_alarm` as `e_stop_active AND NOT e_stop_nc`. This distinguishes an actual E-stop press from a wiring fault (both contacts reading the same state).

### 5.3 Holding Registers (Addresses 100-105)

The engine reads six registers in a single bulk read starting at address 100.

| Address | Tag Name | Scale Factor | Units | Description |
|---------|----------|-------------|-------|-------------|
| 100 | item_count | 1x (raw) | count | Items that have reached SensorEnd since last reset |
| 101 | motor_speed | 1x (raw) | % (0-100) | Motor speed percentage |
| 102 | motor_current | 0.1x (raw / 10) | Amps | Motor current draw |
| 103 | temperature | 0.1x (raw / 10) | Degrees C | Motor or enclosure temperature |
| 104 | pressure | 1x (raw) | PSI | Pneumatic system pressure |
| 105 | error_code | 1x (raw) | — | PLC error code (see table below) |

**Error Code Reference:**

| Code | Meaning |
|------|---------|
| 0 | OK — no fault |
| 1 | Overload |
| 2 | Overheat |
| 3 | Conveyor jam |
| 4 | Sensor fault |
| 5 | Communications fault |

### 5.4 Tag Names in the Diagnosis Engine

The live PLC reader (`read_live_plc()` in `diagnosis_engine.py`) maps Modbus addresses to the following tag dictionary keys, which are then formatted into the Cosmos R2 prompt:

```
conveyor_running    motor_running       motor_stopped
emitter_active      sensor_1_active     sensor_2_active
run_command         switch_center       switch_right
e_stop_active       e_stop_nc           pushbutton
fault_alarm         item_count          motor_speed
motor_current       temperature         pressure
error_code
```

### 5.5 Factory I/O Modbus Driver Setup

1. In Factory I/O, go to **File -> Drivers**
2. Select **Modbus TCP/IP Server** from the driver list
3. Click **Configuration**
4. Map Factory I/O signals to Modbus addresses matching the coil map above:
   - `Conveyor Belt (Speed)` -> Coil 0
   - `Emitter (Active)` -> Coil 1
   - `Sensor (SensorStart)` -> Coil 2
   - `Sensor (SensorEnd)` -> Coil 3
5. Click **Apply** and then **Connect**

The Modbus server in Factory I/O listens on `127.0.0.1:502` when running locally. For remote access via the PLC laptop, the host is `192.168.1.100:502` (the Micro 820's address when it acts as the Modbus master/client that controls Factory I/O).

---

## 6. Simulated PLC Scenarios

The `--simulate-plc` flag loads a pre-built tag dictionary without requiring any hardware. Five scenarios are implemented, covering the most common fault conditions.

### normal

System running at steady state with no faults.

| Tag | Value |
|-----|-------|
| motor_running | True |
| motor_stopped | False |
| motor_speed | 65% |
| motor_current | 2.3 A |
| temperature | 42.0 C |
| pressure | 78 PSI |
| conveyor_running | True |
| conveyor_speed | 50% |
| sensor_1_active | False |
| sensor_2_active | False |
| fault_alarm | False |
| e_stop_active | False |
| error_code | 0 (OK) |

Expected diagnosis: System operating normally. All parameters within safe ranges.

### jam

Conveyor jam with motor overcurrent. Both photoeyes blocked simultaneously, motor fighting against a mechanical obstruction.

| Tag | Value |
|-----|-------|
| motor_running | True |
| motor_stopped | False |
| motor_speed | 45% |
| motor_current | 5.8 A (above 5.0A threshold) |
| temperature | 68.0 C (elevated) |
| pressure | 72 PSI |
| conveyor_running | True |
| conveyor_speed | 50% |
| sensor_1_active | True (both sensors blocked) |
| sensor_2_active | True (both sensors blocked) |
| fault_alarm | True |
| e_stop_active | False |
| error_code | 3 (Jam) |

Expected diagnosis: CRITICAL — Conveyor jam detected. Motor overcurrent (5.8A > 5.0A threshold). Do not restart without clearing the obstruction.

### estop

Emergency stop pressed. All motion halted. System requires safety review before restart.

| Tag | Value |
|-----|-------|
| motor_running | False |
| motor_stopped | True |
| motor_speed | 0% |
| motor_current | 0.0 A |
| temperature | 55.0 C |
| pressure | 75 PSI |
| conveyor_running | False |
| conveyor_speed | 0% |
| sensor_1_active | False |
| sensor_2_active | False |
| fault_alarm | True |
| e_stop_active | True |
| error_code | 0 |

Expected diagnosis: EMERGENCY — E-stop active. Requires safety review. Verify area is clear before reset.

### idle

System stopped normally, ready to start. No faults active.

| Tag | Value |
|-----|-------|
| motor_running | False |
| motor_stopped | True |
| motor_speed | 0% |
| motor_current | 0.0 A |
| temperature | 25.0 C |
| pressure | 80 PSI |
| conveyor_running | False |
| conveyor_speed | 0% |
| sensor_1_active | False |
| sensor_2_active | False |
| fault_alarm | False |
| e_stop_active | False |
| error_code | 0 (OK) |

Expected diagnosis: System idle. Ready to start. No faults detected.

### overheat

Motor running but overheating. Temperature above the 80 C critical alarm threshold. System at risk of thermal damage.

| Tag | Value |
|-----|-------|
| motor_running | True |
| motor_stopped | False |
| motor_speed | 80% |
| motor_current | 4.5 A |
| temperature | 85.0 C (above 80.0 C threshold) |
| pressure | 70 PSI |
| conveyor_running | True |
| conveyor_speed | 80% |
| sensor_1_active | False |
| sensor_2_active | False |
| fault_alarm | True |
| e_stop_active | False |
| error_code | 2 (Overheat) |

Expected diagnosis: CRITICAL — High temperature alarm (85.0 C). Check cooling fan. Do not continue operation without addressing thermal condition.

---

## 7. Fault Detection Reference

Before involving Cosmos R2, the engine runs a deterministic fault classifier (`diagnosis/conveyor_faults.py`) over the PLC tag snapshot. This serves two purposes: it produces instant results for obvious faults (zero LLM latency), and it injects structured fault evidence into the R2 prompt to guide reasoning.

The classifier output appears in the prompt under `## Automated Fault Analysis` and tells R2 what the rules already found. R2 is then instructed to cross-check this against the visual evidence.

### Fault Codes and Trigger Conditions

| Code | Severity | Title | Trigger Condition | Threshold |
|------|----------|-------|-------------------|-----------|
| E001 | EMERGENCY | Emergency Stop Active | `e_stop_active == True` | Any |
| M001 | CRITICAL | Motor Overcurrent | `motor_running AND motor_current > 5.0` | 5.0 A |
| T001 | CRITICAL | High Temperature Alarm | `temperature > 80.0` | 80.0 C |
| C001 | CRITICAL | Conveyor Jam Detected | `motor_running AND conveyor_running AND sensor_1_active AND sensor_2_active` | Both sensors simultaneously active |
| M002 | CRITICAL | Motor Stopped Unexpectedly | `NOT motor_running AND conveyor_speed > 0 AND NOT e_stop_active` | Speed setpoint nonzero |
| P001 | WARNING | Low Pneumatic Pressure | `pressure < 60 AND motor_running` | 60 PSI |
| M003 | WARNING | Motor Speed Mismatch | `motor_running AND motor_speed < 30 AND conveyor_speed > 50` | Speed ratio |
| T002 | WARNING | Elevated Temperature | `65.0 < temperature <= 80.0` | 65-80 C range |
| PLC### | CRITICAL | PLC Fault (generic) | `fault_alarm AND error_code > 0` | Any nonzero error code |
| OK | INFO | System Running Normally | No faults AND motor running AND conveyor running | — |
| IDLE | INFO | System Idle | No faults AND motor stopped AND conveyor stopped | — |

Faults are sorted by severity before being injected into the prompt: EMERGENCY first, then CRITICAL, WARNING, INFO.

### Severity Levels

| Severity | Meaning | Typical Action |
|----------|---------|---------------|
| EMERGENCY | E-stop or safety interlock active | Safety review required before any action |
| CRITICAL | Equipment stopped or at risk — immediate attention required | Stop, diagnose, repair before restarting |
| WARNING | Degraded operation — monitor closely | Investigate at next opportunity; do not ignore |
| INFO | Normal operation note | No action required |

---

## 8. Prompt Architecture

All prompt templates are stored in `cookoff/prompts/factory_diagnosis.yaml`. The engine selects the appropriate template based on what data is available.

### Template Selection Logic

| Condition | Template Used |
|-----------|--------------|
| PLC data available + question provided | `user_question` |
| PLC data available, no question | `user_diagnosis` |
| No PLC data (video only) | `user_describe` |

### System Prompt

The system prompt instructs Cosmos R2 to act as a factory diagnostics AI with four responsibilities:

1. Observe what is happening in the video/image feed
2. Cross-reference visual observations with PLC telemetry data
3. Identify anomalies, faults, or unsafe conditions
4. Provide a clear diagnosis with evidence from BOTH modalities

The key instruction: **when video and PLC data disagree, flag the discrepancy** — this often indicates the root cause. For example, if the motor register reads ON but the video shows no belt movement, the model should identify a likely wiring fault, broken drive coupling, or stuck actuator.

### user_diagnosis Template

Used for general diagnosis with PLC data. Injects:
- Formatted PLC register snapshot (digital I/O booleans as ON/OFF, analog registers as scaled values)
- Automated fault analysis output from the rule engine
- Instructions to produce a `<think>` chain-of-thought block followed by a plain-language diagnosis

### user_question Template

Same as `user_diagnosis` but adds a `## Technician Question` section with the user's specific question. The model is instructed to answer the question using evidence from both the visual feed and the PLC data.

### user_describe Template

Used when no PLC data is available. Asks the model to describe:
- Equipment visible (conveyors, motors, sensors, actuators)
- Current operational state (running, stopped, faulted)
- Any visible anomalies or safety concerns
- Motion and product flow

### Cosmos R2 Sampling Parameters

These parameters follow NVIDIA's published recommendations for Cosmos Reason2-8B in reasoning mode:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `temperature` | `0.6` | Recommended for R2 reasoning mode — not too deterministic, not too random |
| `top_p` | `0.95` | Standard nucleus sampling with R2 |
| `max_tokens` | `4096` | Sufficient for full chain-of-thought reasoning; increase to 8192 for very detailed analyses |

### Response Parsing

Cosmos R2 returns responses with `<think>...</think>` blocks containing the chain-of-thought reasoning, followed by the plain-language diagnosis. The engine parses these blocks:

```python
# From diagnosis_engine.py
if "<think>" in content and "</think>" in content:
    reasoning = content[think_start:think_end].strip()
    diagnosis_text = content[think_end + len("</think>"):].strip()
```

The parsed `reasoning` and `diagnosis` fields are returned separately, allowing the Telegram interface to surface just the diagnosis while the full reasoning is preserved for dashboard or audit use.

---

## 9. Architecture Overview

```
+------------------------------------------------------------------+
|                     TECHNICIAN INTERFACE                         |
|   Phone / Telegram Bot  ->  "Is the conveyor jammed?"           |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                      CLOUD AI LAYER                              |
|   Vast.ai L40S GPU                                               |
|   +------------------------------------------------------+       |
|   |  vLLM serving nvidia/Cosmos-Reason2-8B               |       |
|   |  OpenAI-compatible: /v1/chat/completions              |       |
|   |  Context: 256K tokens | Chain-of-thought: <think>    |       |
|   +------------------------------------------------------+       |
|   +------------------------------------------------------+       |
|   |  diagnosis_engine.py                                  |       |
|   |  - Encodes image/video as base64                      |       |
|   |  - Formats PLC snapshot as structured text            |       |
|   |  - Runs rule-based pre-filter (8 fault codes)         |       |
|   |  - Injects all context into YAML prompt template      |       |
|   |  - Parses <think> chain-of-thought from response      |       |
|   +------------------------------------------------------+       |
+------------------------------------------------------------------+
                              |
                        SSH Tunnel / Tailscale VPN
                              |
+---------------------------+   +----------------------------------+
|    PLC LAPTOP              |   |    EDGE DEVICE (Raspberry Pi)    |
|    (100.72.2.99)           |   |                                  |
|  +--------------------+   |   |  +---------------------------+   |
|  |  Factory I/O Sim   |   |   |  |  factorylm-edge/          |   |
|  |  "From A to B"     |<--+---+->|  Modbus TCP Server        |   |
|  |  scene             |   |   |  |  GPIO bridge for PLC I/O  |   |
|  +--------------------+   |   |  +---------------------------+   |
|  +--------------------+   |   |  +---------------------------+   |
|  |  Allen-Bradley     |   |   |  |  edge_gateway.py          |   |
|  |  Micro 820 PLC     |<--+   +->|  Polls coils 0-17         |   |
|  |  Modbus TCP :502   |   |   |  |  Polls registers 100-105  |   |
|  +--------------------+   |   |  +---------------------------+   |
+---------------------------+   +----------------------------------+
                   |
          Modbus TCP (port 502)
                   |
+------------------------------------------------------------------+
|                   PHYSICAL HARDWARE LAYER                        |
|   Allen-Bradley Micro 820 PLC  (192.168.1.100)                   |
|   - 18 coils: Conveyor, Emitter, Sensors, E-stop, DI/DO         |
|   - Holding registers 100-105: speed, current, temp, pressure   |
|   Physical I/O panel: 3-pos switch, E-stop, pushbutton, LEDs    |
+------------------------------------------------------------------+
```

### Data Flow for a Diagnostic Request

1. Technician sends a message or a photo to the Telegram bot
2. Orchestrator (VPS at `100.68.120.99`) triggers a capture: `capture_fio.py` records a 15-second MP4 from the Factory I/O window
3. Simultaneously, `edge_gateway.py` (or `diagnosis_engine.py --live-plc`) reads coils 0-17 and holding registers 100-105 via Modbus TCP
4. `diagnosis_engine.py` builds the multimodal prompt:
   - Video or image encoded as base64
   - PLC snapshot formatted as structured text (digital I/O: ON/OFF, analog: scaled values)
   - Fault pre-analysis from `conveyor_faults.py` injected as structured evidence
5. The assembled payload is POSTed to the vLLM endpoint
6. Cosmos R2 returns a response with `<think>` chain-of-thought followed by the diagnosis
7. The engine parses the response and returns: `reasoning`, `diagnosis`, `usage` (token counts), `elapsed_s`
8. The Telegram bot delivers the diagnosis back to the technician's phone

### Key Files

| File | Purpose |
|------|---------|
| `cookoff/capture_fio.py` | Screen recorder — 4 FPS MP4 or PNG from Factory I/O window |
| `cookoff/diagnosis_engine.py` | Orchestrator — builds multimodal prompt, calls R2, parses response |
| `cookoff/prompts/factory_diagnosis.yaml` | Structured prompt templates (system + 3 user variants) |
| `diagnosis/conveyor_faults.py` | Rule-based fault classifier — 8 fault codes, 4 severity levels |
| `config/factoryio.yaml` | Coil and register map, poll interval, matrix URL |
| `services/plc-modbus/CLAUDE.md` | Micro 820 hardware config and coil map reference |

---

## 10. Cost Management

### Current Balance and Burn Rate

| Item | Value |
|------|-------|
| Vast.ai credit balance | $66.00 |
| L40S spot price | ~$0.50-0.53/hr |
| Estimated hours remaining | ~124 hours |
| Typical session duration | 1-2 hours |
| Typical session cost | ~$0.50-$1.06 |

### Rules for Cost Control

1. **Always destroy the instance when done.** This is the most important rule. An idle L40S left running overnight costs $4-6 for no benefit.

2. **Verify destruction.** After `destroy instance`, run `show instances` and confirm the instance is gone from the list.

3. **Do not keep instances "warm."** Model loading takes 5-10 minutes on first start, but subsequent starts on a new instance are the same cost. There is no benefit to keeping an instance running between sessions.

4. **Use `--simulate-plc` for development.** When developing or testing prompt changes, use simulated PLC scenarios instead of live hardware. This avoids time spent troubleshooting PLC connectivity on the clock.

5. **Batch your captures.** Run all scenario captures in a single Factory I/O session before spinning up the GPU. Media capture does not require the GPU to be running.

### Checking Your Balance

```bash
"C:/Users/hharp/AppData/Local/Python/pythoncore-3.14-64/Scripts/vastai.exe" show user
```

Look for the `credit` field in the output.

### Checking Running Instances

```bash
"C:/Users/hharp/AppData/Local/Python/pythoncore-3.14-64/Scripts/vastai.exe" show instances
```

An empty output means no instances are running and no charges are accumulating.

---

## 11. Troubleshooting

### "Connection timed out" when using --live-plc

**Symptom:** `WARNING: Cannot connect to PLC at 192.168.1.100:502` followed by `Falling back to video-only diagnosis.`

**Causes and fixes:**

1. **Ethernet cable not plugged in.** The Micro 820 communicates via Ethernet only. Verify the cable is seated at both ends (PC NIC and PLC Ethernet port). The NIC link LED should be solid or blinking.

2. **Wrong subnet.** Your PC must be on `192.168.1.x/24`. Check with `ipconfig` (Windows) and look for the adapter connected to the PLC. The IP should be `192.168.1.50` or similar.

3. **PLC not powered.** The Micro 820 power LED should be on. If the panel is off, check the power supply.

4. **Transient Modbus error.** Modbus TCP can fail with a timeout on the first read after an idle period. Run the diagnosis command again — the second attempt usually succeeds.

5. **Factory I/O Modbus driver not connected.** In Factory I/O, check the driver status. Click "Connect" if it shows "Disconnected."

### "Media disconnected" in ipconfig

The Ethernet adapter shows "Media disconnected." The physical cable is not plugged in or is not seated properly. Re-seat the cable at both ends. Some cables have a locking tab that must click in.

### Unicode errors on Windows (UnicodeEncodeError, UnicodeDecodeError)

**Symptom:** Diagnosis output prints garbled characters or throws a `UnicodeEncodeError` before printing anything.

**Status:** Fixed in `diagnosis_engine.py`. The engine wraps `sys.stdout` and `sys.stderr` with UTF-8 encoding at startup:

```python
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
```

If you still encounter this, verify you are running from the correct virtual environment and that the version of `diagnosis_engine.py` in use is the current one (check the top of the file for these lines).

### vLLM not responding (curl hangs or connection refused)

**Check 1: Is the SSH tunnel active?**

```bash
# List active SSH processes
ps aux | grep ssh
```

On Windows (Git Bash or WSL):
```bash
netstat -an | grep 8000
```

If the tunnel process is gone, re-run the tunnel command from Step 3 of Quick Start.

**Check 2: Is the vLLM server running?**

SSH back into the instance:
```bash
ssh -i ~/.ssh/id_ed25519 -p <PORT> root@<SSH_HOST>
tail -100 /tmp/vllm.log
```

Look for:
- `"Application startup complete"` — server is running, tunnel problem
- Error messages about CUDA out of memory — use `--gpu-memory-utilization 0.85` instead of `0.9`
- Process not found — vLLM crashed; re-run the `nohup vllm serve ...` command

**Check 3: Health endpoint**

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`. If this returns a response, the tunnel and server are both working and the issue is in the diagnosis engine request formatting.

### SSH tunnel died mid-session

The tunnel process can die if your local machine sleeps, the network drops, or the Vast.ai instance restarts. Re-run the tunnel command:

```bash
ssh -i ~/.ssh/id_ed25519 -p <PORT> -f -N -L 8000:localhost:8000 root@<SSH_HOST>
```

If you get `Address already in use` for port 8000, a previous tunnel is still bound. Kill it first:

```bash
# On Windows (Git Bash)
netstat -ano | grep :8000
# Find the PID in the last column, then:
taskkill /PID <PID> /F
```

Then re-run the tunnel command.

### ffmpeg not found (video recording fails)

**Symptom:** `record_clip` prints `ffmpeg error:` and falls back to saving raw frames.

**Fix:** Install ffmpeg and add it to your PATH.

1. Download from https://ffmpeg.org/download.html (Windows builds: https://www.gyan.dev/ffmpeg/builds/)
2. Extract and add the `bin/` folder to your Windows PATH environment variable
3. Open a new terminal and verify: `ffmpeg -version`

Alternatively, if you only need images, use `screenshot` mode instead of `record`. The diagnosis engine accepts PNG images with `--image`.

### "File not found" for image or video path

Shell glob patterns like `cookoff/clips/my_test_*.png` are expanded by the shell, not Python. If you get "File not found", the glob did not match anything. Check that the capture completed successfully and that the file exists in `cookoff/clips/`:

```bash
ls cookoff/clips/
```

Use the full filename with timestamp in the diagnosis command, or use a shell that expands globs (bash, not Windows cmd.exe).

### Model response is very slow (>60 seconds)

Normal response time on a fresh L40S with a screenshot-sized image is 15-30 seconds. Longer times indicate:

- **Large video file:** A 30-second clip at 4 FPS base64-encodes to several hundred MB. Transfer over the SSH tunnel can take significant time. Use shorter clips (15 seconds) for routine diagnostics.
- **Instance under load:** Check if another process on the instance is consuming GPU memory. SSH in and run `nvidia-smi`.
- **Network bottleneck:** The tunnel transfers the entire base64-encoded media payload. On a slow connection, reduce clip duration or use screenshots instead.

### Vast.ai instance shows "loading" indefinitely

The instance is still pulling the Docker image or initializing. Wait up to 10 minutes. If it does not reach `running` state, destroy it and create a new one with a different offer (some hosts are unreliable).

---

*FactoryLM Vision — NVIDIA Cosmos Cookoff Entry*
*Repository: https://github.com/Mikecranesync/factorylm*
*Last updated: February 2026*
