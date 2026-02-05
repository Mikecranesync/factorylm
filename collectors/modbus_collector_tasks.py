"""
BeagleBone Modbus RTU Collector - Celery Tasks
===============================================
Collects data from BeagleBone via Modbus RTU (serial) or TCP.
"""

import os
import sys
sys.path.insert(0, '/opt/master_of_puppets')

from celery_app import app
from collectors.base_collector import BaseCollector, get_influx_writer
from typing import Dict, Any, List, Tuple


# Default configuration
MODBUS_PORT = os.getenv("MODBUS_PORT", "/dev/ttyUSB0")  # Serial port
MODBUS_IP = os.getenv("MODBUS_IP", "192.168.0.3")      # For TCP mode
MODBUS_MODE = os.getenv("MODBUS_MODE", "rtu")          # rtu or tcp
MODBUS_UNIT = int(os.getenv("MODBUS_UNIT", "1"))       # Slave ID

# Register map configuration
# Format: (address, count, register_type, tag_name, scale_factor)
# register_type: "holding" (3x), "input" (4x), "coil" (0x), "discrete" (1x)
DEFAULT_REGISTERS = [
    (0, 1, "holding", "motor_speed", 0.1),      # Register 40001, scale by 0.1
    (1, 1, "holding", "motor_temp", 0.1),       # Register 40002
    (2, 1, "holding", "vibration", 0.01),       # Register 40003
    (3, 1, "holding", "current", 0.01),         # Register 40004
    (10, 1, "holding", "pressure", 0.1),        # Register 40011
    (20, 1, "input", "ambient_temp", 0.1),      # Register 30021
]


class ModbusCollector(BaseCollector):
    """Modbus RTU/TCP data collector using pymodbus."""
    
    def __init__(self, mode: str = MODBUS_MODE, port: str = MODBUS_PORT, 
                 ip: str = MODBUS_IP, unit: int = MODBUS_UNIT):
        super().__init__(
            name="modbus_collector",
            vendor="beaglebone_modbus",
            ip=ip if mode == "tcp" else port,
            port=502 if mode == "tcp" else None
        )
        self.mode = mode
        self.serial_port = port
        self.tcp_ip = ip
        self.unit = unit
        self.client = None
        self.registers = DEFAULT_REGISTERS
    
    def connect(self) -> bool:
        """Connect to Modbus device."""
        try:
            from pymodbus.client import ModbusSerialClient, ModbusTcpClient
            
            if self.mode == "rtu":
                self.client = ModbusSerialClient(
                    port=self.serial_port,
                    baudrate=9600,
                    parity='N',
                    stopbits=1,
                    bytesize=8,
                    timeout=3
                )
            else:  # tcp
                self.client = ModbusTcpClient(
                    host=self.tcp_ip,
                    port=502,
                    timeout=3
                )
            
            self.connected = self.client.connect()
            
            if self.connected:
                self.logger.info(f"Connected to Modbus ({self.mode}) at {self.ip}")
            return self.connected
            
        except ImportError:
            self.logger.error("pymodbus not installed. Run: pip install pymodbus")
            return False
        except Exception as e:
            self.logger.error(f"Modbus connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from Modbus device."""
        if self.client:
            try:
                self.client.close()
                self.connected = False
                return True
            except:
                pass
        return False
    
    def read_data(self) -> Dict[str, Any]:
        """Read configured registers from Modbus device."""
        if not self.client or not self.connected:
            raise ConnectionError("Not connected to Modbus device")
        
        data = {}
        
        for addr, count, reg_type, tag_name, scale in self.registers:
            try:
                if reg_type == "holding":
                    result = self.client.read_holding_registers(addr, count, slave=self.unit)
                elif reg_type == "input":
                    result = self.client.read_input_registers(addr, count, slave=self.unit)
                elif reg_type == "coil":
                    result = self.client.read_coils(addr, count, slave=self.unit)
                elif reg_type == "discrete":
                    result = self.client.read_discrete_inputs(addr, count, slave=self.unit)
                else:
                    self.logger.warning(f"Unknown register type: {reg_type}")
                    continue
                
                if result.isError():
                    self.logger.warning(f"Failed to read {tag_name}: {result}")
                    data[tag_name] = None
                else:
                    # Get raw value and apply scale
                    if reg_type in ("coil", "discrete"):
                        value = result.bits[0] if result.bits else None
                    else:
                        raw = result.registers[0] if result.registers else None
                        # Handle signed values (if > 32767, treat as negative)
                        if raw is not None and raw > 32767:
                            raw = raw - 65536
                        value = round(raw * scale, 3) if raw is not None else None
                    
                    data[tag_name] = value
                    
            except Exception as e:
                self.logger.warning(f"Failed to read {tag_name}: {e}")
                data[tag_name] = None
        
        return data
    
    def configure_registers(self, registers: List[Tuple]):
        """Configure which registers to read."""
        self.registers = registers


# Global collector instance
_collector = None

def get_collector() -> ModbusCollector:
    global _collector
    if _collector is None:
        _collector = ModbusCollector()
    return _collector


@app.task(bind=True, name='modbus_collector.collect')
def collect(self) -> Dict[str, Any]:
    """
    Collect data from Modbus device.
    Called periodically by Celery Beat.
    """
    collector = get_collector()
    result = collector.collect()
    
    # Write to InfluxDB if we got data
    if "data" in result and result["data"]:
        writer = get_influx_writer()
        writer.write(
            measurement="plc_data",
            tags={"vendor": "beaglebone_modbus", "plc_ip": collector.ip},
            fields=result["data"]
        )
    
    return result


@app.task(bind=True, name='modbus_collector.status')
def status(self) -> Dict[str, Any]:
    """Get collector status."""
    return get_collector().get_status()


@app.task(bind=True, name='modbus_collector.configure')
def configure(self, mode: str = None, port: str = None, ip: str = None, 
              unit: int = None) -> Dict[str, Any]:
    """Reconfigure the collector."""
    global _collector
    _collector = ModbusCollector(
        mode=mode or MODBUS_MODE,
        port=port or MODBUS_PORT,
        ip=ip or MODBUS_IP,
        unit=unit if unit is not None else MODBUS_UNIT
    )
    return {"status": "reconfigured", "mode": _collector.mode, "ip": _collector.ip}


@app.task(bind=True, name='modbus_collector.health')
def health(self) -> Dict[str, Any]:
    """Health check."""
    return {"status": "ok", "agent": "ModbusCollector", "connected": get_collector().connected}
