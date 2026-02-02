# FactoryLM Complete Setup Guide
## From Unboxing Micro 820 to LLM-Powered HMI

This is the complete guide from opening your Micro 820 box to having an LLM answer questions about your factory simulation.

---

## Table of Contents

- [Phase A: Hardware Unboxing & Physical Setup](#phase-a-hardware-unboxing--physical-setup)
- [Phase B: Software Installation](#phase-b-software-installation)
- [Phase C: Micro 820 First-Time Configuration](#phase-c-micro-820-first-time-configuration)
- [Phase D: Factory I/O Configuration](#phase-d-factory-io-configuration)
- [Phase E: Python Modbus Connection Test](#phase-e-python-modbus-connection-test)
- [Phase F: LLM Integration](#phase-f-llm-integration)
- [Phase G: Complete Checklist](#phase-g-complete-checklist)
- [Troubleshooting](#troubleshooting)

---

## Phase A: Hardware Unboxing & Physical Setup

### A1. What's in the Micro 820 Box

**Allen-Bradley Micro 820 (2080-LC20-20QWB or similar)**
- Micro 820 controller unit
- Power terminal block (if not pre-installed)
- Documentation CD/QR code
- Quick start guide

**You'll Also Need (not included):**
- 24V DC power supply (2A minimum)
- Ethernet cable (Cat5e or better)
- USB-A to USB-B cable (for initial programming)
- Laptop/PC with Windows
- Screwdriver for terminal connections

### A2. Physical Connections

```
                    ┌─────────────────────────────┐
                    │      MICRO 820 PLC          │
   ┌────────────────┼─────────────────────────────┼────────────────┐
   │                │                             │                │
   │   24V DC IN    │     ETHERNET PORT           │   USB PORT     │
   │   (L+ / L-)    │     (to your network)       │   (programming)│
   │                │                             │                │
   └────────────────┴─────────────────────────────┴────────────────┘
```

**Step-by-Step:**

1. **Mount the PLC** (DIN rail or panel)
   - Ensure adequate ventilation
   - Keep away from high-heat sources

2. **Connect Power**
   ```
   24V DC Power Supply
   ├── L+ (positive) → Micro 820 L+ terminal
   └── L- (negative) → Micro 820 L- terminal
   ```
   - **DO NOT power on yet**

3. **Connect Ethernet**
   - Plug Ethernet cable into PLC's Ethernet port
   - Connect other end to:
     - Your PC directly (for initial setup), OR
     - Your network switch (same subnet as PC)

4. **Connect USB (optional but recommended for first setup)**
   - USB-B into PLC
   - USB-A into PC
   - Provides reliable connection for initial configuration

---

## Phase B: Software Installation

### B1. Install Connected Components Workbench (CCW)

**Download CCW:**
1. Go to: https://www.rockwellautomation.com/en-us/products/software/factorytalk/designsuite/connected-components-workbench.html
2. Create/login to Rockwell account (free)
3. Download CCW (currently v21.00 or newer)
4. Run installer as Administrator

**During Installation:**
- Select "Typical" installation
- Include all Micro800 components
- Install USB drivers when prompted

**After Installation:**
- Restart PC
- Launch CCW to verify installation
- Accept license agreement

### B2. Install Factory I/O

**Download Factory I/O:**
1. Go to: https://factoryio.com/
2. Download trial or purchase license
3. Run installer

**Post-Installation:**
- Launch Factory I/O
- Select "Sorting by Height" scene (simplest demo scene)
- Go to **File > Drivers** - note the available drivers

### B3. Install Python Environment

```powershell
# Open PowerShell as Administrator

# Install Python (if not installed)
winget install Python.Python.3.11

# Verify installation
python --version  # Should show 3.11.x

# Create project folder
mkdir C:\FactoryLM
cd C:\FactoryLM

# Create virtual environment
python -m venv venv

# Activate environment
.\venv\Scripts\Activate

# Install required packages
pip install pymodbus python-dotenv groq
```

---

## Phase C: Micro 820 First-Time Configuration

### C1. Power On the PLC

1. Double-check all connections
2. Turn on 24V power supply
3. Wait for PLC to boot (30-60 seconds)
4. Observe LED indicators:
   - **PWR** (green) = Power OK
   - **RUN** (green) = Controller running
   - **FAULT** (red) = Problem (should be OFF)
   - **ETHERNET** (green/blinking) = Network active

### C2. Configure IP Address via CCW

**Launch CCW and Create Project:**

1. Open Connected Components Workbench
2. **File > New > Micro800 Application**
3. Select your controller:
   - **2080-LC20-20QWB** (20-point I/O) or your model
4. Name project: "FactoryLM_Demo"
5. Click OK

**Set Ethernet IP Address:**

1. In Project Tree, expand **Controller**
2. Double-click **Ethernet**
3. Configure:
   ```
   IP Address:      192.168.1.100
   Subnet Mask:     255.255.255.0
   Default Gateway: 192.168.1.1  (or your router)
   ```
4. **Important:** Ensure "DHCP Enabled" is UNCHECKED (use static IP)

**Configure Your PC's IP (same subnet):**

```powershell
# PowerShell - Set static IP on your Ethernet adapter
# Adjust adapter name as needed

# Find your adapter name
Get-NetAdapter

# Set IP (example - adjust adapter name)
New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.1.50 -PrefixLength 24 -DefaultGateway 192.168.1.1
```

Or use Windows Network Settings:
1. Control Panel > Network > Adapter Settings
2. Right-click Ethernet adapter > Properties
3. IPv4 > Properties > Use static:
   - IP: 192.168.1.50
   - Subnet: 255.255.255.0
   - Gateway: 192.168.1.1

### C3. Enable Modbus TCP Server

**In CCW Project:**

1. In Project Tree, click **Controller Properties**
2. Go to **Modbus Mapping** tab
3. Check **"Enable Modbus TCP Server"**
4. Set **Port: 502** (default)
5. Set **Unit ID: 1**

**Create Global Variables for HMI Access:**

1. In Project Tree, double-click **Global Variables**
2. Add these variables:

| Name | Type | Initial Value | Comment |
|------|------|---------------|---------|
| motor_speed | INT | 0 | Motor speed 0-100% |
| motor_current | INT | 0 | Current in 0.1A units |
| temperature | INT | 250 | Temp in 0.1C (250 = 25.0C) |
| pressure | INT | 100 | Pressure in PSI |
| motor_running | BOOL | FALSE | Motor status |
| motor_stopped | BOOL | TRUE | Motor stopped status |
| fault_alarm | BOOL | FALSE | Fault indicator |
| conveyor_running | BOOL | FALSE | Conveyor status |
| sensor_1 | BOOL | FALSE | Part at sensor 1 |
| sensor_2 | BOOL | FALSE | Part at sensor 2 |

3. **Map Variables to Modbus Addresses:**
   - Right-click each variable > **Modbus Mapping**
   - Assign addresses:

   | Variable | Modbus Type | Address |
   |----------|-------------|---------|
   | motor_speed | Holding Register | 100 |
   | motor_current | Holding Register | 101 |
   | temperature | Holding Register | 102 |
   | pressure | Holding Register | 103 |
   | motor_running | Coil | 0 |
   | motor_stopped | Coil | 1 |
   | fault_alarm | Coil | 2 |
   | conveyor_running | Coil | 3 |
   | sensor_1 | Coil | 4 |
   | sensor_2 | Coil | 5 |

### C4. Create Simple Ladder Logic

**In CCW, open Main Program:**

1. Double-click **Programs > MainProgram**
2. Create a simple motor control rung:

```
Rung 1: Motor Start Logic
─────────────────────────────────────────────────────────────────
│                                                                │
├──[Start_Button]──┬──[/Stop_Button]──[/Fault]──( motor_running )│
│                  │                                             │
├──[motor_running]─┘                                             │
│                                                                │
─────────────────────────────────────────────────────────────────

Rung 2: Motor Stopped Status
─────────────────────────────────────────────────────────────────
│                                                                │
├──[/motor_running]──────────────────────────( motor_stopped )   │
│                                                                │
─────────────────────────────────────────────────────────────────

Rung 3: Simulate Temperature (increases when motor runs)
─────────────────────────────────────────────────────────────────
│                                                                │
├──[motor_running]──[ADD: temperature + 1 > temperature]──       │
│                                                                │
│  (Only runs when motor_running, temp increases over time)      │
─────────────────────────────────────────────────────────────────
```

For a demo without real I/O, add simulation rungs:
- Motor speed follows a fixed value when running
- Temperature slowly increases when motor runs
- Current is proportional to speed

### C5. Download to PLC

1. Click **Connect** button (or press F7)
2. Select connection method:
   - **USB** (if connected) - most reliable for first time
   - **Ethernet** (if IP already configured)
3. Click **Download** (or Ctrl+D)
4. Select **"Download All"**
5. When prompted, put PLC in **RUN** mode
6. Verify:
   - RUN LED is green (solid)
   - No FAULT LED
   - Ethernet LED blinking

---

## Phase D: Factory I/O Configuration

### D1. Select Simplest Scene

**For demo/development, use "Sorting by Height (Basic)":**

1. Launch Factory I/O
2. **File > New > Scenes**
3. Select **"Sorting by Height (Basic)"**
4. Click **Open**

**Scene Components:**
- Entry conveyor with parts
- Height sensor
- Two sorting conveyors
- Light sensors for part detection

### D2. Configure Modbus TCP Driver

1. **File > Drivers**
2. Select **"Modbus TCP/IP Client"**
3. Click **Configuration** (gear icon)
4. Set:
   ```
   Server IP: 192.168.1.100  (your Micro 820)
   Port: 502
   Unit ID: 1
   Poll Rate: 100ms  (or faster for responsive simulation)
   ```

### D3. Map Factory I/O I/O to Modbus

In the Driver Configuration window:

**Outputs (Factory I/O > PLC via Modbus Coils):**

| Factory I/O Output | Modbus Coil Address | Purpose |
|-------------------|---------------------|---------|
| Entry Conveyor | Coil 0 | motor_running |
| Sorter Conveyor 1 | Coil 3 | conveyor_running |
| Sorter Actuator | Coil 6 | (optional) |

**Inputs (PLC > Factory I/O via Modbus Discrete Inputs):**

| Factory I/O Input | Modbus DI Address | Purpose |
|------------------|-------------------|---------|
| Height Sensor (analog) | Holding Reg 104 | Part height reading |
| Sensor At Entry | DI 0 | sensor_1 |
| Sensor At Exit | DI 1 | sensor_2 |

### D4. Test the Connection

1. Click **Play** (green triangle) in Factory I/O
2. Watch the simulation run
3. In CCW, open **Watch Window** (View > Watch)
4. Add your global variables
5. Verify:
   - `motor_running` changes when conveyor runs
   - `sensor_1`/`sensor_2` toggle as parts pass
   - `temperature` slowly increases

**Troubleshooting:**
- No connection? Check firewall (allow port 502)
- Wrong values? Verify Modbus address mapping
- Nothing moves? Check Factory I/O driver is set to "Client" not "Server"

---

## Phase E: Python Modbus Connection Test

### E1. Simple Connection Test

Create file: `C:\FactoryLM\test_connection.py`

See the `scripts/test_connection.py` file in this repository.

**Run the test:**
```powershell
cd C:\FactoryLM
.\venv\Scripts\Activate
python test_connection.py
```

### E2. Expected Output

```
==================================================
FactoryLM - Micro 820 Connection Test
==================================================
Connecting to Micro 820 at 192.168.1.100:502...
Connected!

Reading Holding Registers 100-105...
  Register 100 (motor_speed):   75
  Register 101 (motor_current): 2.5 A
  Register 102 (temperature):   32.5 C
  Register 103 (pressure):      100 PSI
  Register 104 (conveyor_speed):50
  Register 105 (error_code):    0

Reading Coils 0-5...
  Coil 0 (motor_running):    True
  Coil 1 (motor_stopped):    False
  Coil 2 (fault_alarm):      False
  Coil 3 (conveyor_running): True
  Coil 4 (sensor_1):         False
  Coil 5 (sensor_2):         True
```

---

## Phase F: LLM Integration

### F1. Install FactoryLM Core

```powershell
cd C:\FactoryLM
.\venv\Scripts\Activate

# If you have it locally:
pip install -e C:\Users\hharp\OneDrive\Desktop\FactoryLM\core
```

### F2. Configure LLM Provider

Create: `C:\FactoryLM\.env`

```bash
# PLC Configuration
PLC_TYPE=micro820
PLC_HOST=192.168.1.100
PLC_PORT=502

# LLM Configuration (choose one)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# Alternative: Claude
# LLM_PROVIDER=claude
# ANTHROPIC_API_KEY=sk-ant-your_key_here

# Alternative: DeepSeek
# LLM_PROVIDER=deepseek
# DEEPSEEK_API_KEY=your_key_here
```

### F3. Run the LLM Demo

```powershell
cd C:\FactoryLM
.\venv\Scripts\Activate
python llm_demo.py
```

**Expected Interaction:**
```
============================================================
  FactoryLM - LLM-Powered Factory Assistant
  Connected to Micro 820 via Modbus TCP
============================================================

Reading initial PLC state...

CURRENT FACTORY STATE (live data from Micro 820 PLC):
Motor Status:     RUNNING
Motor Speed:      75%
Motor Current:    2.5 A
Temperature:      45.2C
Pressure:         100 PSI
...

You: Why is the temperature at 45 degrees?

FactoryLM: The temperature of 45.2C is within normal operating range
(20-60C). This is expected when the motor has been running at 75% speed
for a period of time. The motor generates heat during operation, and 45C
indicates proper cooling. No action needed, but monitor if it continues
rising above 50C.
```

---

## Phase G: Complete Checklist

### Hardware Setup
- [ ] Micro 820 unpacked and mounted
- [ ] 24V DC power connected
- [ ] Ethernet cable connected to PC/network
- [ ] PLC powered on, RUN LED green

### Software Setup
- [ ] CCW installed and licensed
- [ ] Factory I/O installed
- [ ] Python 3.11+ installed
- [ ] Virtual environment created

### CCW Configuration
- [ ] Project created for Micro 820
- [ ] IP address set to 192.168.1.100
- [ ] Modbus TCP Server enabled
- [ ] Global variables created (motor_speed, temperature, etc.)
- [ ] Modbus address mapping configured (Reg 100-105, Coils 0-5)
- [ ] Simple ladder logic written
- [ ] Program downloaded to PLC

### Factory I/O Configuration
- [ ] Scene loaded ("Sorting by Height" recommended)
- [ ] Modbus TCP Client driver selected
- [ ] Server IP set to 192.168.1.100:502
- [ ] I/O points mapped to Modbus addresses
- [ ] Simulation running and responding

### Python/LLM Integration
- [ ] test_connection.py runs successfully
- [ ] Can read registers and coils
- [ ] .env file configured with API keys
- [ ] llm_demo.py runs and responds to questions

---

## Troubleshooting

### "Cannot connect to PLC"
1. Verify IP addresses are on same subnet
2. Ping the PLC: `ping 192.168.1.100`
3. Check Windows Firewall (allow port 502)
4. Verify Modbus TCP Server enabled in CCW
5. Ensure PLC is in RUN mode

### "Register read error"
1. Verify Modbus address mapping in CCW
2. Check Unit ID matches (usually 1)
3. Ensure variables are mapped to correct register types

### "Factory I/O not responding"
1. Check driver is "Client" not "Server"
2. Verify Server IP matches PLC IP
3. Restart Factory I/O driver
4. Check poll rate isn't too fast (100ms minimum)

### "LLM not responding"
1. Verify API key in .env
2. Check internet connection
3. Verify GROQ/Anthropic account has credits

---

## Next Steps

After completing this guide:

1. **Voice HMI (PRD-002)**: Add voice interface for hands-free operation
2. **Web Dashboard (PRD-004)**: Real-time browser-based monitoring
3. **ML Training (Phase 4)**: Predictive maintenance from historical data
