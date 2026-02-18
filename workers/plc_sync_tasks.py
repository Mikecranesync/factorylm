"""
PLC SYNC - Real-Time PLC I/O Synchronization
=============================================
Reads/writes Micro820 PLC via Modbus or CIP,
syncs state with demo visualization.

Target: Micro820 PLC connected to PLC laptop
Protocol: Modbus TCP (primary) or CIP
"""

import os
import sys
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import logging

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_celery_tracing

logger = logging.getLogger(__name__)

# PLC Connection config
PLC_HOST = os.getenv('PLC_HOST', '192.168.1.100')  # Local network from PLC laptop
PLC_PORT = int(os.getenv('PLC_PORT', '502'))  # Modbus TCP
MODBUS_UNIT_ID = 1

# State file for demo sync
STATE_FILE = Path('/opt/master_of_puppets/state/plc_io_state.json')

# Address mapping for demo
# Format: logical_name -> (modbus_address, bit_offset, description)
IO_MAP = {
    # Discrete Inputs (I:0/x)
    'start_button': (0, 0, 'Start pushbutton'),
    'stop_button': (0, 1, 'Stop pushbutton'),
    'sensor_1': (0, 2, 'Conveyor sensor 1'),
    'sensor_2': (0, 3, 'Conveyor sensor 2'),
    'e_stop': (0, 4, 'Emergency stop'),
    
    # Discrete Outputs (O:0/x)
    'conveyor_motor': (16, 0, 'Conveyor motor'),
    'red_light': (16, 1, 'Red stack light'),
    'yellow_light': (16, 2, 'Yellow stack light'),
    'green_light': (16, 3, 'Green stack light'),
    'alarm_horn': (16, 4, 'Alarm horn'),
    
    # Analog (demonstration)
    'speed_setpoint': (40001, None, 'Conveyor speed setpoint'),
    'actual_speed': (40002, None, 'Actual conveyor speed'),
}


class PLCBridge(BaseAgent):
    """
    Bridge between VPS and Micro820 PLC.
    
    Two modes of operation:
    1. Direct: VPS connects to PLC (if exposed via Tailscale)
    2. Relay: VPS -> PLC Laptop -> PLC (via local network)
    
    For demo, we use Relay mode since PLC is on local network.
    """
    
    def __init__(self):
        super().__init__("PLCBridge")
        self._client = None
        self._connected = False
        self._last_state: Dict[str, Any] = {}
        self._load_state()
    
    def _load_state(self):
        """Load last known I/O state."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    self._last_state = json.load(f)
            except:
                self._last_state = {}
    
    def _save_state(self):
        """Save current I/O state."""
        STATE_FILE.parent.mkdir(exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(self._last_state, f, indent=2)
    
    def _ensure_connected(self) -> bool:
        """Connect to PLC via Modbus TCP."""
        if self._connected and self._client:
            return True
        
        try:
            from pymodbus.client import ModbusTcpClient
            self._client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
            if self._client.connect():
                self._connected = True
                self.logger.info(f"Connected to PLC at {PLC_HOST}:{PLC_PORT}")
                return True
            else:
                self.logger.error("Modbus connection failed")
                return False
                
        except ImportError:
            self.logger.warning("pymodbus not installed")
            return False
        except Exception as e:
            self.logger.error(f"PLC connection error: {e}")
            return False
    
    def read_discrete_inputs(self, start_address: int = 0, count: int = 8) -> dict:
        """Read discrete inputs (I:0/x)."""
        if not self._ensure_connected():
            # Return simulated state for demo
            return self._get_simulated_inputs()
        
        try:
            result = self._client.read_discrete_inputs(start_address, count, unit=MODBUS_UNIT_ID)
            if result.isError():
                return {"error": str(result)}
            
            bits = result.bits[:count]
            state = {f"I:0/{i}": bits[i] for i in range(count)}
            self._last_state.update(state)
            self._save_state()
            return {"inputs": state, "raw": bits}
            
        except Exception as e:
            return {"error": str(e)}
    
    def read_coils(self, start_address: int = 16, count: int = 8) -> dict:
        """Read coils/outputs (O:0/x)."""
        if not self._ensure_connected():
            return self._get_simulated_outputs()
        
        try:
            result = self._client.read_coils(start_address, count, unit=MODBUS_UNIT_ID)
            if result.isError():
                return {"error": str(result)}
            
            bits = result.bits[:count]
            state = {f"O:0/{i}": bits[i] for i in range(count)}
            self._last_state.update(state)
            self._save_state()
            return {"outputs": state, "raw": bits}
            
        except Exception as e:
            return {"error": str(e)}
    
    def write_coil(self, address: int, value: bool) -> dict:
        """Write single coil/output."""
        if not self._ensure_connected():
            # Simulate write
            self._last_state[f"O:0/{address-16}"] = value
            self._save_state()
            return {"simulated": True, "address": address, "value": value}
        
        try:
            result = self._client.write_coil(address, value, unit=MODBUS_UNIT_ID)
            if result.isError():
                return {"error": str(result)}
            return {"success": True, "address": address, "value": value}
        except Exception as e:
            return {"error": str(e)}
    
    def force_output(self, name: str, value: bool) -> dict:
        """
        Force an output by logical name.
        
        Example: force_output('conveyor_motor', True)
        """
        if name not in IO_MAP:
            return {"error": f"Unknown I/O: {name}"}
        
        addr, bit, desc = IO_MAP[name]
        if addr < 16:
            return {"error": f"{name} is an input, cannot force"}
        
        result = self.write_coil(addr + bit if bit else addr, value)
        result['name'] = name
        result['description'] = desc
        return result
    
    def read_all_io(self) -> dict:
        """Read all inputs and outputs."""
        inputs = self.read_discrete_inputs()
        outputs = self.read_coils()
        
        # Map to logical names
        named_io = {}
        for name, (addr, bit, desc) in IO_MAP.items():
            if bit is not None:
                if addr < 16:
                    key = f"I:0/{bit}"
                    named_io[name] = inputs.get('inputs', {}).get(key, False)
                else:
                    key = f"O:0/{bit}"
                    named_io[name] = outputs.get('outputs', {}).get(key, False)
        
        return {
            "named_io": named_io,
            "raw_inputs": inputs,
            "raw_outputs": outputs,
            "timestamp": datetime.now().isoformat()
        }
    
    def generate_mermaid_diagram(self) -> str:
        """
        Generate Mermaid diagram of current I/O state.
        
        This is what Mike referenced - the I/O visualization.
        """
        io_state = self.read_all_io()
        named = io_state.get('named_io', {})
        
        # Build Mermaid flowchart
        lines = [
            "```mermaid",
            "flowchart LR",
            "    subgraph Inputs",
        ]
        
        # Inputs
        for name, (addr, bit, desc) in IO_MAP.items():
            if addr < 16:
                state = "🟢" if named.get(name, False) else "⚪"
                lines.append(f"        {name}[{state} {desc}]")
        
        lines.append("    end")
        lines.append("    subgraph PLC[Micro820]")
        lines.append("        logic((Logic))")
        lines.append("    end")
        lines.append("    subgraph Outputs")
        
        # Outputs
        for name, (addr, bit, desc) in IO_MAP.items():
            if addr >= 16 and bit is not None:
                state = "🟢" if named.get(name, False) else "⚪"
                lines.append(f"        {name}[{state} {desc}]")
        
        lines.append("    end")
        lines.append("")
        
        # Connections
        for name, (addr, bit, desc) in IO_MAP.items():
            if addr < 16:
                lines.append(f"    {name} --> logic")
            elif bit is not None:
                lines.append(f"    logic --> {name}")
        
        lines.append("```")
        
        return "\n".join(lines)
    
    def _get_simulated_inputs(self) -> dict:
        """Return simulated input state for demo."""
        return {
            "inputs": {
                "I:0/0": self._last_state.get("I:0/0", False),
                "I:0/1": self._last_state.get("I:0/1", False),
                "I:0/2": self._last_state.get("I:0/2", True),  # Sensor active
                "I:0/3": self._last_state.get("I:0/3", False),
                "I:0/4": self._last_state.get("I:0/4", False),  # E-stop OK
            },
            "simulated": True
        }
    
    def _get_simulated_outputs(self) -> dict:
        """Return simulated output state for demo."""
        return {
            "outputs": {
                "O:0/0": self._last_state.get("O:0/0", False),
                "O:0/1": self._last_state.get("O:0/1", False),
                "O:0/2": self._last_state.get("O:0/2", True),  # Yellow light
                "O:0/3": self._last_state.get("O:0/3", False),
                "O:0/4": self._last_state.get("O:0/4", False),
            },
            "simulated": True
        }


# Singleton
_bridge = None

def get_bridge() -> PLCBridge:
    global _bridge
    if _bridge is None:
        _bridge = PLCBridge()
    return _bridge


# =============================================================================
# CELERY TASKS
# =============================================================================

@app.task(bind=True, name='plc.read_inputs')
@with_celery_tracing
def read_inputs(self) -> dict:
    """Read all PLC inputs."""
    return get_bridge().read_discrete_inputs()


@app.task(bind=True, name='plc.read_outputs')
@with_celery_tracing
def read_outputs(self) -> dict:
    """Read all PLC outputs."""
    return get_bridge().read_coils()


@app.task(bind=True, name='plc.read_all')
@with_celery_tracing
def read_all_io(self) -> dict:
    """Read all I/O with logical names."""
    return get_bridge().read_all_io()


@app.task(bind=True, name='plc.read_address')
@with_celery_tracing
def read_plc_address(self, address: str) -> dict:
    """
    Read a specific PLC address.
    
    address: 'I:0/0', 'O:0/3', or logical name like 'conveyor_motor'
    """
    bridge = get_bridge()
    
    # Check if it's a logical name
    if address in IO_MAP:
        io_state = bridge.read_all_io()
        return {
            "address": address,
            "value": io_state['named_io'].get(address),
            "description": IO_MAP[address][2]
        }
    
    # Parse address format (I:0/x or O:0/x)
    if address.startswith('I:'):
        inputs = bridge.read_discrete_inputs()
        return {"address": address, "value": inputs.get('inputs', {}).get(address)}
    elif address.startswith('O:'):
        outputs = bridge.read_coils()
        return {"address": address, "value": outputs.get('outputs', {}).get(address)}
    
    return {"error": f"Unknown address format: {address}"}


@app.task(bind=True, name='plc.force')
@with_celery_tracing
def force_plc_output(self, address: str, value: int) -> dict:
    """
    Force a PLC output.
    
    address: 'O:0/0' or logical name like 'conveyor_motor'
    value: 0 or 1
    """
    bridge = get_bridge()
    value_bool = bool(value)
    
    # Logical name
    if address in IO_MAP:
        return bridge.force_output(address, value_bool)
    
    # Direct address O:0/x
    if address.startswith('O:0/'):
        bit = int(address.split('/')[1])
        return bridge.write_coil(16 + bit, value_bool)
    
    return {"error": f"Cannot force address: {address}"}


@app.task(bind=True, name='plc.mermaid')
@with_celery_tracing
def generate_mermaid(self) -> dict:
    """Generate Mermaid I/O diagram."""
    diagram = get_bridge().generate_mermaid_diagram()
    
    # Also save to file
    output_path = Path('/root/jarvis-workspace/projects/yc-demo/io_diagram.md')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(f"# PLC I/O State - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(diagram)
    
    return {
        "diagram": diagram,
        "saved_to": str(output_path)
    }


@app.task(bind=True, name='plc.demo_sequence')
@with_celery_tracing
def run_demo_sequence(self) -> dict:
    """
    Run a demonstration sequence showing I/O changes.
    
    1. Start conveyor
    2. Show sensor triggers
    3. Cycle through lights
    """
    import time
    bridge = get_bridge()
    sequence_results = []
    
    # Step 1: Start conveyor
    result = bridge.force_output('conveyor_motor', True)
    sequence_results.append({"step": "Start conveyor", "result": result})
    time.sleep(2)
    
    # Step 2: Green light
    bridge.force_output('green_light', True)
    bridge.force_output('yellow_light', False)
    bridge.force_output('red_light', False)
    sequence_results.append({"step": "Green light ON"})
    time.sleep(3)
    
    # Step 3: Yellow light (warning)
    bridge.force_output('green_light', False)
    bridge.force_output('yellow_light', True)
    sequence_results.append({"step": "Yellow light ON"})
    time.sleep(2)
    
    # Step 4: Stop conveyor, red light
    bridge.force_output('conveyor_motor', False)
    bridge.force_output('yellow_light', False)
    bridge.force_output('red_light', True)
    sequence_results.append({"step": "Stop, red light ON"})
    
    return {
        "sequence": "demo_complete",
        "steps": sequence_results,
        "final_state": bridge.read_all_io()
    }


if __name__ == "__main__":
    # Test
    bridge = get_bridge()
    print(bridge.read_all_io())
    print(bridge.generate_mermaid_diagram())
