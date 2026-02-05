"""
S7-1200 Data Collector - Celery Tasks
=====================================
Collects data from Siemens S7-1200 PLC using python-snap7.
"""

import os
import sys
sys.path.insert(0, '/opt/master_of_puppets')

from celery_app import app
from collectors.base_collector import BaseCollector, get_influx_writer
from typing import Dict, Any, List


# Default configuration
S7_IP = os.getenv("S7_IP", "192.168.0.1")
S7_RACK = int(os.getenv("S7_RACK", "0"))
S7_SLOT = int(os.getenv("S7_SLOT", "1"))

# Data block configuration (customize for your PLC program)
# Format: (db_number, start_byte, size_bytes, data_type, tag_name)
DEFAULT_TAGS = [
    (1, 0, 4, "REAL", "motor_speed"),
    (1, 4, 4, "REAL", "motor_temp"),
    (1, 8, 4, "REAL", "vibration"),
    (1, 12, 4, "REAL", "current"),
]


class S7Collector(BaseCollector):
    """Siemens S7-1200/1500 data collector using snap7."""
    
    def __init__(self, ip: str = S7_IP, rack: int = S7_RACK, slot: int = S7_SLOT):
        super().__init__(
            name="s7_collector",
            vendor="siemens_s7",
            ip=ip,
            port=102  # ISO-on-TCP
        )
        self.rack = rack
        self.slot = slot
        self.client = None
        self.tags = DEFAULT_TAGS
    
    def connect(self) -> bool:
        """Connect to S7 PLC."""
        try:
            import snap7
            from snap7.util import get_real
            
            self.client = snap7.client.Client()
            self.client.connect(self.ip, self.rack, self.slot)
            self.connected = self.client.get_connected()
            
            if self.connected:
                self.logger.info(f"Connected to S7 PLC at {self.ip}")
            return self.connected
            
        except ImportError:
            self.logger.error("snap7 not installed. Run: pip install python-snap7")
            return False
        except Exception as e:
            self.logger.error(f"S7 connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from S7 PLC."""
        if self.client:
            try:
                self.client.disconnect()
                self.connected = False
                return True
            except:
                pass
        return False
    
    def read_data(self) -> Dict[str, Any]:
        """Read configured tags from S7 PLC."""
        if not self.client or not self.connected:
            raise ConnectionError("Not connected to PLC")
        
        import snap7
        from snap7.util import get_real, get_int, get_bool
        
        data = {}
        
        for db_num, start, size, dtype, tag_name in self.tags:
            try:
                raw = self.client.db_read(db_num, start, size)
                
                if dtype == "REAL":
                    value = get_real(raw, 0)
                elif dtype == "INT":
                    value = get_int(raw, 0)
                elif dtype == "BOOL":
                    value = get_bool(raw, 0, 0)
                else:
                    value = raw.hex()
                
                data[tag_name] = round(value, 3) if isinstance(value, float) else value
                
            except Exception as e:
                self.logger.warning(f"Failed to read {tag_name}: {e}")
                data[tag_name] = None
        
        return data
    
    def configure_tags(self, tags: List[tuple]):
        """Configure which tags to read."""
        self.tags = tags


# Global collector instance
_collector = None

def get_collector() -> S7Collector:
    global _collector
    if _collector is None:
        _collector = S7Collector()
    return _collector


@app.task(bind=True, name='s7_collector.collect')
def collect(self) -> Dict[str, Any]:
    """
    Collect data from S7-1200 PLC.
    Called periodically by Celery Beat.
    """
    collector = get_collector()
    result = collector.collect()
    
    # Write to InfluxDB if we got data
    if "data" in result and result["data"]:
        writer = get_influx_writer()
        writer.write(
            measurement="plc_data",
            tags={"vendor": "siemens_s7", "plc_ip": collector.ip},
            fields=result["data"]
        )
    
    return result


@app.task(bind=True, name='s7_collector.status')
def status(self) -> Dict[str, Any]:
    """Get collector status."""
    return get_collector().get_status()


@app.task(bind=True, name='s7_collector.configure')
def configure(self, ip: str = None, rack: int = None, slot: int = None) -> Dict[str, Any]:
    """Reconfigure the collector."""
    global _collector
    _collector = S7Collector(
        ip=ip or S7_IP,
        rack=rack if rack is not None else S7_RACK,
        slot=slot if slot is not None else S7_SLOT
    )
    return {"status": "reconfigured", "ip": _collector.ip}


@app.task(bind=True, name='s7_collector.health')
def health(self) -> Dict[str, Any]:
    """Health check."""
    return {"status": "ok", "agent": "S7Collector", "connected": get_collector().connected}
