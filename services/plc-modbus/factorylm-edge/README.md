# FactoryLM Edge Device

Modbus TCP server for Raspberry Pi that bridges Factory I/O simulation to physical GPIO.

## Quick Start

### On the Raspberry Pi

```bash
# Clone or copy files to Pi
git clone https://github.com/Mikecranesync/factorylm-edge.git
cd factorylm-edge

# Run installer
bash install.sh

# Start server (requires sudo for port 502)
sudo python edge_server.py

# Or test on port 5020 without sudo
python edge_server.py --port 5020
```

### From Your Development Machine

```python
from pymodbus.client import ModbusTcpClient

# Connect to Pi
client = ModbusTcpClient('192.168.1.200', port=502, timeout=3)
client.connect()

# Read inputs (buttons/sensors on coils 0-9)
result = client.read_coils(address=0, count=10)
print(f"Inputs: {result.bits[:10]}")

# Write outputs (LEDs/relays on coils 10-19)
client.write_coil(address=10, value=True)   # LED Green ON
client.write_coil(address=11, value=False)  # LED Red OFF

client.close()
```

## Hardware Setup

### Default GPIO Mapping

| Function | Coil | GPIO Pin (BCM) | Physical Pin |
|----------|------|----------------|--------------|
| Start Button | 0 | GPIO17 | Pin 11 |
| Stop Button | 1 | GPIO27 | Pin 13 |
| E-Stop | 2 | GPIO22 | Pin 15 |
| LED Green | 10 | GPIO5 | Pin 29 |
| LED Red | 11 | GPIO6 | Pin 31 |
| Relay 1 | 12 | GPIO13 | Pin 33 |
| Relay 2 | 13 | GPIO19 | Pin 35 |

### Wiring Diagram

```
Raspberry Pi GPIO Header (looking at Pi with USB ports down)

     3V3  (1) (2)  5V
   GPIO2  (3) (4)  5V
   GPIO3  (5) (6)  GND
   GPIO4  (7) (8)  GPIO14
     GND  (9) (10) GPIO15
  GPIO17 (11) (12) GPIO18     <- Pin 11: Start Button
  GPIO27 (13) (14) GND        <- Pin 13: Stop Button
  GPIO22 (15) (16) GPIO23     <- Pin 15: E-Stop
     3V3 (17) (18) GPIO24
  GPIO10 (19) (20) GND
   GPIO9 (21) (22) GPIO25
  GPIO11 (23) (24) GPIO8
     GND (25) (26) GPIO7
   GPIO0 (27) (28) GPIO1
   GPIO5 (29) (30) GND        <- Pin 29: LED Green
   GPIO6 (31) (32) GPIO12     <- Pin 31: LED Red
  GPIO13 (33) (34) GND        <- Pin 33: Relay 1
  GPIO19 (35) (36) GPIO16     <- Pin 35: Relay 2
  GPIO26 (37) (38) GPIO20
     GND (39) (40) GPIO21
```

## Configuration

Edit `config.json` to customize your I/O mapping:

```json
{
    "name": "My Custom Setup",
    "inputs": [
        {"coil": 0, "gpio": 17, "name": "Start_Button"},
        {"coil": 1, "gpio": 27, "name": "Stop_Button"}
    ],
    "outputs": [
        {"coil": 10, "gpio": 5, "name": "Motor_Run"},
        {"coil": 11, "gpio": 6, "name": "Motor_Fault"}
    ]
}
```

### Factory I/O Scene Presets

Use `gpio_mapping.py` to view/select Factory I/O scene configurations:

```bash
# List all available scenes
python gpio_mapping.py

# Show specific scene config
python gpio_mapping.py sorting_basic
python gpio_mapping.py pick_and_place
python gpio_mapping.py micro820_mirror
```

## Service Management

```bash
# Enable auto-start on boot
sudo systemctl enable factorylm-edge

# Start the service
sudo systemctl start factorylm-edge

# Check status
sudo systemctl status factorylm-edge

# View logs
sudo journalctl -u factorylm-edge -f

# Stop service
sudo systemctl stop factorylm-edge
```

## Integration with Main Project

Add to your FastAPI backend to communicate with both Micro820 and Pi:

```python
from pymodbus.client import ModbusTcpClient

# Main PLC
plc_client = ModbusTcpClient('192.168.1.100', port=502)

# Edge device (Pi)
edge_client = ModbusTcpClient('192.168.1.200', port=502)

# Read from both
plc_state = plc_client.read_coils(0, 18)
edge_state = edge_client.read_coils(0, 20)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Permission denied | Run with `sudo` or use `--port 5020` |
| Port 502 in use | `sudo lsof -i :502` to find process |
| GPIO not available | Install `RPi.GPIO`: `pip install RPi.GPIO` |
| Cannot connect | Check IP with `hostname -I`, test with `nc -zv IP 502` |

## Files

- `edge_server.py` - Main Modbus TCP server with GPIO sync
- `gpio_mapping.py` - Pin configurations for Factory I/O scenes
- `config.json` - Runtime configuration
- `requirements.txt` - Python dependencies
- `install.sh` - One-command setup script

## Requirements

- Raspberry Pi 3B+, 4, or 5
- Raspberry Pi OS (Bullseye or newer)
- Python 3.9+
- Network connection (Ethernet recommended)
