# Scene: From A to B

Factory I/O "From A to B" scene connected to a real Allen-Bradley Micro 820 PLC, controllable remotely via Modbus TCP.

## I/O Mapping

| PLC Global Variable | Type | Modbus Address | Factory I/O Signal | Direction |
|---------------------|------|----------------|-------------------|-----------|
| `Conveyor` | BOOL | Coil 0 | Conveyor | PLC → FIO |
| `Emitter` | BOOL | Coil 1 | Emitter | PLC → FIO |
| `SensorStart` | BOOL | Coil 2 | Sensor Start | FIO → PLC |
| `SensorEnd` | BOOL | Coil 3 | Sensor End | FIO → PLC |
| `RunCommand` | BOOL | Coil 4 | — | Remote trigger |
| `ItemCount` | INT | Register 100 | — | Counter |

## CCW Setup (Step-by-Step)

### 1. Create Project
1. Open **Connected Components Workbench (CCW)**
2. File → New → Micro 800 → **Micro 820**
3. Set controller IP: **192.168.1.100** (Controller Properties → Ethernet tab)

### 2. Enable Modbus TCP Server
1. In the project tree, double-click **Controller Properties**
2. Go to the **Modbus TCP** tab
3. Check **Enable Modbus TCP Server**
4. Leave port at **502**

### 3. Create Global Variables
1. In the project tree, expand **Global Variables**
2. Add each variable exactly as shown:

| Name | Data Type | Initial Value |
|------|-----------|---------------|
| `Conveyor` | BOOL | FALSE |
| `Emitter` | BOOL | FALSE |
| `SensorStart` | BOOL | FALSE |
| `SensorEnd` | BOOL | FALSE |
| `RunCommand` | BOOL | FALSE |
| `ItemCount` | INT | 0 |

### 4. Create Modbus Mapping
1. In the project tree, double-click **Modbus Mapping**
2. Map each variable to its Modbus address:

| Modbus Type | Address | Variable |
|-------------|---------|----------|
| Coil | 0 | Conveyor |
| Coil | 1 | Emitter |
| Coil | 2 | SensorStart |
| Coil | 3 | SensorEnd |
| Coil | 4 | RunCommand |
| Holding Register | 100 | ItemCount |

### 5. Paste ST Program
1. In the project tree, expand **Programs** → double-click **MainProgram**
2. Set language to **Structured Text** (if not already)
3. In the **Local Variables** section, add:
   - `SensorEnd_Prev` : BOOL := FALSE
4. Paste the contents of `from_a_to_b.st` into the code editor (only the logic portion — skip the comment headers with VAR declarations)

### 6. Build and Download
1. **Build**: Press **F7** (or Build → Build)
2. Fix any errors shown in the output window
3. **Download**: Press **Ctrl+F5** (or Controller → Download)
4. Select the controller at 192.168.1.100
5. Confirm the download
6. **Run**: Switch controller to **Run** mode (Controller → Run)

### 7. Verify via Modbus
From the PLC laptop terminal:
```bash
cd C:\Users\hharp\Desktop\factorylm-monorepo\services\plc-modbus
python -c "
from pymodbus.client import ModbusTcpClient
c = ModbusTcpClient('192.168.1.100', port=502, timeout=3)
c.connect()
coils = c.read_coils(0, 5)
print('Coils 0-4:', [int(b) for b in coils.bits[:5]])
regs = c.read_holding_registers(100, 1)
print('ItemCount:', regs.registers[0])
c.close()
"
```

## Factory I/O Setup

### 1. Launch Factory I/O
```
"C:\Program Files (x86)\Real Games\Factory IO\Factory IO.exe"
```

### 2. Open Scene
File → Open → **"1 - From A to B"**

### 3. Configure Driver
1. File → Drivers
2. Select **Allen-Bradley Micro 8x0 (CCW)** from the driver list
3. Click **Configuration**
4. Set PLC IP: **192.168.1.100**

### 4. Map I/O Tags
In the driver configuration, map Factory I/O tags to PLC global variables:

| Factory I/O Tag | Direction | PLC Variable |
|-----------------|-----------|-------------|
| Conveyor | Output | Conveyor |
| Emitter | Output | Emitter |
| Sensor Start | Input | SensorStart |
| Sensor End | Input | SensorEnd |

### 5. Run
1. Press **Play** (F5) in Factory I/O
2. The simulation is now connected to the live PLC

## Remote Control Test

Start the conveyor from any Tailnet device:
```bash
# Connect to PLC
curl -X POST http://100.72.2.99:8001/api/plc/connect \
  -H "Content-Type: application/json" \
  -d '{"ip": "192.168.1.100", "port": 502}'

# Start conveyor (write RunCommand = TRUE)
curl -X POST http://100.72.2.99:8001/api/plc/write-coil \
  -H "Content-Type: application/json" \
  -d '{"address": 4, "value": true}'

# Check I/O
curl http://100.72.2.99:8001/api/plc/io

# Stop conveyor
curl -X POST http://100.72.2.99:8001/api/plc/write-coil \
  -H "Content-Type: application/json" \
  -d '{"address": 4, "value": false}'
```
