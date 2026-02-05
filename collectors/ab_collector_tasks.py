"""
Micro820 Data Collector - Celery Tasks
======================================
Collects data from Allen-Bradley Micro820 using pycomm3 (EtherNet/IP).
"""

import os
import sys
sys.path.insert(0, '/opt/master_of_puppets')

from celery_app import app
from collectors.base_collector import BaseCollector, get_influx_writer
from typing import Dict, Any, List


# Default configuration
AB_IP = os.getenv("AB_IP", "192.168.0.2")

# Tag configuration (customize for your PLC program)
DEFAULT_TAGS = [
    "Motor_Speed",
    "Motor_Temp",
    "Vibration",
    "Current",
    "Run_Status",
]


class ABCollector(BaseCollector):
    """Allen-Bradley Micro820/CompactLogix collector using pycomm3."""
    
    def __init__(self, ip: str = AB_IP):
        super().__init__(
            name="ab_collector",
            vendor="allen_bradley",
            ip=ip,
            port=44818  # EtherNet/IP
        )
        self.plc = None
        self.tags = DEFAULT_TAGS
    
    def connect(self) -> bool:
        """Connect to AB PLC via EtherNet/IP."""
        try:
            from pycomm3 import LogixDriver
            
            self.plc = LogixDriver(self.ip)
            self.plc.open()
            self.connected = True
            self.logger.info(f"Connected to AB PLC at {self.ip}")
            return True
            
        except ImportError:
            self.logger.error("pycomm3 not installed. Run: pip install pycomm3")
            return False
        except Exception as e:
            self.logger.error(f"AB connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from AB PLC."""
        if self.plc:
            try:
                self.plc.close()
                self.connected = False
                return True
            except:
                pass
        return False
    
    def read_data(self) -> Dict[str, Any]:
        """Read configured tags from AB PLC."""
        if not self.plc or not self.connected:
            raise ConnectionError("Not connected to PLC")
        
        data = {}
        
        # Read all tags at once (more efficient)
        try:
            results = self.plc.read(*self.tags)
            
            # Handle single vs multiple results
            if not isinstance(results, list):
                results = [results]
            
            for result in results:
                if result.error:
                    self.logger.warning(f"Failed to read {result.tag}: {result.error}")
                    data[result.tag] = None
                else:
                    value = result.value
                    # Round floats for cleaner output
                    if isinstance(value, float):
                        value = round(value, 3)
                    data[result.tag] = value
                    
        except Exception as e:
            self.logger.error(f"Batch read failed: {e}")
            raise
        
        return data
    
    def configure_tags(self, tags: List[str]):
        """Configure which tags to read."""
        self.tags = tags


# Global collector instance
_collector = None

def get_collector() -> ABCollector:
    global _collector
    if _collector is None:
        _collector = ABCollector()
    return _collector


@app.task(bind=True, name='ab_collector.collect')
def collect(self) -> Dict[str, Any]:
    """
    Collect data from Micro820 PLC.
    Called periodically by Celery Beat.
    """
    collector = get_collector()
    result = collector.collect()
    
    # Write to InfluxDB if we got data
    if "data" in result and result["data"]:
        writer = get_influx_writer()
        writer.write(
            measurement="plc_data",
            tags={"vendor": "allen_bradley", "plc_ip": collector.ip},
            fields=result["data"]
        )
    
    return result


@app.task(bind=True, name='ab_collector.status')
def status(self) -> Dict[str, Any]:
    """Get collector status."""
    return get_collector().get_status()


@app.task(bind=True, name='ab_collector.configure')
def configure(self, ip: str = None, tags: List[str] = None) -> Dict[str, Any]:
    """Reconfigure the collector."""
    global _collector
    _collector = ABCollector(ip=ip or AB_IP)
    if tags:
        _collector.configure_tags(tags)
    return {"status": "reconfigured", "ip": _collector.ip, "tags": _collector.tags}


@app.task(bind=True, name='ab_collector.health')
def health(self) -> Dict[str, Any]:
    """Health check."""
    return {"status": "ok", "agent": "ABCollector", "connected": get_collector().connected}
