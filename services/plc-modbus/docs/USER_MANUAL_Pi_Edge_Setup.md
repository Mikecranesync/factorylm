# User Manual: Raspberry Pi Edge Device Setup

## Overview

This guide walks you through setting up a Raspberry Pi as a Modbus TCP server that bridges Factory I/O simulation to physical GPIO pins. When complete, you'll be able to control LEDs/relays on the Pi from the same web app that controls your Micro 820 PLC.

**Time Required:** 30-45 minutes

**Prerequisites:**
- Raspberry Pi 3B+, 4, or 5 with Raspberry Pi OS installed
- Pi connected to same network as your PC (192.168.1.x)
- SSH access to Pi enabled
- Optional: LEDs, buttons, or relay board connected to GPIO

---

## Part 1: Prepare Your PC

### Step 1.1: Push Code to GitHub

From your PC terminal (in the factorylm-plc-client directory):

```bash
# Push the commit we just made
git push
```

### Step 1.2: Create the Edge Device Repository (Optional)

If you want a separate repo for the Pi code:

1. Go to https://github.com/new
2. Create repo: `factorylm-edge`
3. Don't initialize with README (we have one)

Then push just the edge code:

```bash
cd factorylm-edge
git init
git add .
git commit -m "Initial commit: Modbus TCP server for Raspberry Pi"
git branch -M main
git remote add origin https://github.com/Mikecranesync/factorylm-edge.git
git push -u origin main
```

---

## Part 2: Find Your Pi's IP Address

### Option A: From the Pi directly

If you have a monitor/keyboard connected:

```bash
hostname -I
```

### Option B: From your router

Check your router's admin page for connected devices. Look for "raspberrypi" or similar.

### Option C: Scan your network

From your PC:

```bash
# Windows (PowerShell)
1..254 | ForEach-Object { Test-Connection -ComputerName "192.168.1.$_" -Count 1 -Quiet }

# Or use the network scanner we built
curl -X POST http://localhost:8000/api/setup/scan-network
```

**Write down your Pi's IP:** `192.168.1.____`

---

## Part 3: Connect to Your Pi

### Step 3.1: Open Terminal/PowerShell

**Windows:** Press `Win + X`, select "Windows Terminal" or "PowerShell"

**Mac/Linux:** Open Terminal

### Step 3.2: SSH into the Pi

```bash
ssh pi@192.168.1.XXX
```

Replace `XXX` with your Pi's IP address.

**Default credentials:**
- Username: `pi`
- Password: `raspberry` (change this later with `passwd`)

**First time connecting?** Type `yes` when asked about the fingerprint.

You should now see:
```
pi@raspberrypi:~ $
```

---

## Part 4: Transfer Files to Pi

### Option A: Using SCP (from a NEW terminal on your PC)

Open a **second terminal** on your PC (keep SSH open):

```bash
# Navigate to your project
cd /mnt/c/Users/hharp/Desktop/factorylm-plc-client

# Copy the entire factorylm-edge folder to Pi
scp -r factorylm-edge/ pi@192.168.1.XXX:~/
```

Enter your Pi password when prompted.

### Option B: Using Git (on the Pi)

In your SSH session on the Pi:

```bash
# If you pushed to a separate repo
git clone https://github.com/Mikecranesync/factorylm-edge.git

# Or clone the main repo and use the subfolder
git clone https://github.com/YOUR_USERNAME/factorylm-plc-client.git
cd factorylm-plc-client/factorylm-edge
```

### Option C: Using VS Code Remote SSH

1. Install "Remote - SSH" extension in VS Code
2. Press `F1` → "Remote-SSH: Connect to Host"
3. Enter `pi@192.168.1.XXX`
4. Open folder `/home/pi/factorylm-edge`
5. Drag and drop files from your PC

---

## Part 5: Install on the Pi

### Step 5.1: Navigate to the folder

In your SSH session:

```bash
cd ~/factorylm-edge
ls -la
```

You should see:
```
edge_server.py
gpio_mapping.py
config.json
requirements.txt
install.sh
README.md
```

### Step 5.2: Run the installer

```bash
bash install.sh
```

This will:
- Update system packages
- Create Python virtual environment
- Install pymodbus, RPi.GPIO, FastAPI
- Create systemd service file
- Create default config if missing

**Wait for "Installation Complete!" message.**

---

## Part 6: Configure GPIO Mapping

### Step 6.1: Review default config

```bash
cat config.json
```

Default mapping:
| Function | Coil | GPIO |
|----------|------|------|
| Start Button | 0 | GPIO17 (Pin 11) |
| Stop Button | 1 | GPIO27 (Pin 13) |
| E-Stop | 2 | GPIO22 (Pin 15) |
| LED Green | 10 | GPIO5 (Pin 29) |
| LED Red | 11 | GPIO6 (Pin 31) |
| Relay 1 | 12 | GPIO13 (Pin 33) |
| Relay 2 | 13 | GPIO19 (Pin 35) |

### Step 6.2: Customize if needed

Edit the config to match your wiring:

```bash
nano config.json
```

Example for different pins:
```json
{
    "name": "My Custom Setup",
    "inputs": [
        {"coil": 0, "gpio": 17, "name": "Start_Button"},
        {"coil": 1, "gpio": 27, "name": "Stop_Button"}
    ],
    "outputs": [
        {"coil": 10, "gpio": 18, "name": "LED_Green"},
        {"coil": 11, "gpio": 23, "name": "LED_Red"}
    ]
}
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 6.3: View Factory I/O presets

```bash
source .venv/bin/activate
python gpio_mapping.py
```

To see a specific scene:
```bash
python gpio_mapping.py sorting_basic
python gpio_mapping.py micro820_mirror
```

---

## Part 7: Start the Server

### Option A: Manual start (for testing)

```bash
cd ~/factorylm-edge
source .venv/bin/activate

# Port 502 requires sudo
sudo .venv/bin/python edge_server.py

# Or use port 5020 without sudo (for testing)
python edge_server.py --port 5020
```

You should see:
```
============================================================
FactoryLM Edge Server
============================================================
Configuration: Factory I/O Default
Server address: 0.0.0.0:502
GPIO mode: Hardware
Inputs: [0, 1, 2] -> GPIO [17, 27, 22]
Outputs: [10, 11, 12, 13] -> GPIO [5, 6, 13, 19]
============================================================
Press Ctrl+C to stop
```

**Keep this terminal open** and proceed to Part 8 for testing.

### Option B: Run as service (for production)

```bash
# Enable auto-start on boot
sudo systemctl enable factorylm-edge

# Start now
sudo systemctl start factorylm-edge

# Check status
sudo systemctl status factorylm-edge
```

To view logs:
```bash
sudo journalctl -u factorylm-edge -f
```

To stop:
```bash
sudo systemctl stop factorylm-edge
```

---

## Part 8: Test from Your PC

### Step 8.1: Quick connection test

Open a **new terminal on your PC**:

```bash
# Test if port 502 is open
nc -zv 192.168.1.XXX 502
```

Should say: `Connection to 192.168.1.XXX 502 port [tcp/*] succeeded!`

### Step 8.2: Python test script

Create a test file or run interactively:

```bash
cd /mnt/c/Users/hharp/Desktop/factorylm-plc-client
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
python
```

```python
from pymodbus.client import ModbusTcpClient

# Connect to Pi (use your Pi's IP)
client = ModbusTcpClient('192.168.1.XXX', port=502, timeout=3)
connected = client.connect()
print(f"Connected: {connected}")

# Read all coils
result = client.read_coils(address=0, count=20)
print(f"Coils 0-19: {result.bits[:20]}")

# Turn on LED Green (coil 10)
client.write_coil(address=10, value=True)
print("LED Green ON")

# Turn on LED Red (coil 11)
client.write_coil(address=11, value=True)
print("LED Red ON")

# Read back outputs
result = client.read_coils(address=10, count=4)
print(f"Outputs (coils 10-13): {result.bits[:4]}")

# Turn off all
client.write_coil(address=10, value=False)
client.write_coil(address=11, value=False)
print("LEDs OFF")

client.close()
```

### Step 8.3: Watch the Pi terminal

If you're running the server manually, you'll see log messages:
```
2026-01-25 15:30:45 - INFO - Write: Coil 10 = True
2026-01-25 15:30:46 - INFO - Write: Coil 11 = True
```

---

## Part 9: Wire Physical Hardware (Optional)

### Basic LED Test Circuit

```
Pi GPIO5 (Pin 29) ──────┬──── 330Ω resistor ──── LED+ ──── LED- ──── GND (Pin 30)
                        │
Pi GPIO6 (Pin 31) ──────┼──── 330Ω resistor ──── LED+ ──── LED- ──── GND
                        │
                       etc.
```

### Button Input Circuit

```
3.3V (Pin 1) ──── Button ──── Pi GPIO17 (Pin 11)
                              │
                              └── 10kΩ resistor ──── GND (Pin 9)
```

### GPIO Pin Reference

```
Physical pins on Pi header (40-pin):

   3V3  (1)  (2)  5V
 GPIO2  (3)  (4)  5V
 GPIO3  (5)  (6)  GND
 GPIO4  (7)  (8)  GPIO14
   GND  (9)  (10) GPIO15
GPIO17 (11)  (12) GPIO18    ← Input: Start Button
GPIO27 (13)  (14) GND       ← Input: Stop Button
GPIO22 (15)  (16) GPIO23    ← Input: E-Stop
   3V3 (17)  (18) GPIO24
GPIO10 (19)  (20) GND
 GPIO9 (21)  (22) GPIO25
GPIO11 (23)  (24) GPIO8
   GND (25)  (26) GPIO7
 GPIO0 (27)  (28) GPIO1
 GPIO5 (29)  (30) GND       ← Output: LED Green
 GPIO6 (31)  (32) GPIO12    ← Output: LED Red
GPIO13 (33)  (34) GND       ← Output: Relay 1
GPIO19 (35)  (36) GPIO16    ← Output: Relay 2
GPIO26 (37)  (38) GPIO20
   GND (39)  (40) GPIO21
```

---

## Part 10: Integrate with Web App

### Update backend config

Edit `backend/config.py` to add edge device:

```python
class Settings(BaseSettings):
    # Existing PLC settings
    plc_ip: str = "192.168.1.100"
    plc_port: int = 502

    # Edge device settings
    edge_ip: str = "192.168.1.XXX"  # Your Pi IP
    edge_port: int = 502
    edge_enabled: bool = True
```

### Add API route

The web app can now control both devices:
- Micro 820 PLC: `192.168.1.100:502`
- Raspberry Pi: `192.168.1.XXX:502`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Permission denied` on port 502 | Use `sudo` or `--port 5020` |
| `Address already in use` | Run `sudo lsof -i :502` to find conflicting process |
| `Connection refused` | Check Pi IP, ensure server is running |
| `RPi.GPIO not found` | Run `pip install RPi.GPIO` in venv |
| GPIO not responding | Verify BCM pin numbers with `pinout` command |
| SSH connection timeout | Check Pi is on network, try `ping 192.168.1.XXX` |

### Useful commands on Pi

```bash
# Check IP address
hostname -I

# Check if server is running
sudo systemctl status factorylm-edge

# View server logs
sudo journalctl -u factorylm-edge -f

# Test GPIO manually
gpio -g mode 5 out
gpio -g write 5 1   # ON
gpio -g write 5 0   # OFF

# Check what's using port 502
sudo lsof -i :502

# Restart server
sudo systemctl restart factorylm-edge
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│  FACTORYLM EDGE DEVICE - QUICK REFERENCE                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SSH TO PI:     ssh pi@192.168.1.XXX                       │
│  START SERVER:  sudo python edge_server.py                  │
│  STOP SERVER:   Ctrl+C (or systemctl stop factorylm-edge)  │
│                                                             │
│  DEFAULT MODBUS MAPPING:                                    │
│  ┌──────────┬──────┬────────┬─────────────┐               │
│  │ Function │ Coil │ GPIO   │ Pin         │               │
│  ├──────────┼──────┼────────┼─────────────┤               │
│  │ Input 0  │  0   │ GPIO17 │ Pin 11      │               │
│  │ Input 1  │  1   │ GPIO27 │ Pin 13      │               │
│  │ Input 2  │  2   │ GPIO22 │ Pin 15      │               │
│  │ Output 0 │ 10   │ GPIO5  │ Pin 29      │               │
│  │ Output 1 │ 11   │ GPIO6  │ Pin 31      │               │
│  │ Output 2 │ 12   │ GPIO13 │ Pin 33      │               │
│  │ Output 3 │ 13   │ GPIO19 │ Pin 35      │               │
│  └──────────┴──────┴────────┴─────────────┘               │
│                                                             │
│  PYTHON TEST:                                               │
│    from pymodbus.client import ModbusTcpClient             │
│    client = ModbusTcpClient('192.168.1.XXX', port=502)     │
│    client.connect()                                         │
│    client.write_coil(10, True)   # Output 0 ON             │
│    client.read_coils(0, 20)      # Read all                │
│                                                             │
│  FILES:                                                     │
│    ~/factorylm-edge/edge_server.py   - Main server         │
│    ~/factorylm-edge/config.json      - GPIO mapping        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Add more I/O**: Connect buttons, sensors, relays
2. **Customize scenes**: Edit `config.json` for your Factory I/O scene
3. **Web integration**: Add Pi to the FastAPI backend
4. **LLM control**: Use natural language to control both PLC and Pi

---

*Manual created for FactoryLM Edge Device v1.0*
*Last updated: January 25, 2026*
