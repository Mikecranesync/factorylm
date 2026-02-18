"""
Base Collector - Common functionality for PLC data collectors
==============================================================
Provides connection handling, retry logic, and InfluxDB writing.
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)


class BaseCollector(ABC):
    """Base class for all PLC data collectors."""
    
    def __init__(self, name: str, vendor: str, ip: str, port: int = None):
        self.name = name
        self.vendor = vendor
        self.ip = ip
        self.port = port
        self.logger = logging.getLogger(f"collector.{name}")
        self.connected = False
        self.last_read = None
        self.read_count = 0
        self.error_count = 0
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to PLC."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from PLC."""
        pass
    
    @abstractmethod
    def read_data(self) -> Dict[str, Any]:
        """Read data from PLC. Returns dict of tag_name: value."""
        pass
    
    def collect(self) -> Dict[str, Any]:
        """Collect data with error handling and metrics."""
        if not self.connected:
            try:
                self.connect()
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"Connection failed: {e}")
                return {"error": str(e), "connected": False}
        
        try:
            data = self.read_data()
            self.last_read = datetime.utcnow()
            self.read_count += 1
            
            return {
                "timestamp": self.last_read.isoformat(),
                "vendor": self.vendor,
                "plc_ip": self.ip,
                "data": data,
                "read_count": self.read_count,
            }
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Read failed: {e}")
            self.connected = False  # Force reconnect on next attempt
            return {"error": str(e), "connected": False}
    
    def get_status(self) -> Dict[str, Any]:
        """Get collector status."""
        return {
            "name": self.name,
            "vendor": self.vendor,
            "ip": self.ip,
            "connected": self.connected,
            "last_read": self.last_read.isoformat() if self.last_read else None,
            "read_count": self.read_count,
            "error_count": self.error_count,
        }


class InfluxDBWriter:
    """Writes data points to InfluxDB."""
    
    def __init__(self, url: str = None, token: str = None, org: str = "factorylm", bucket: str = "sensors"):
        self.url = url or "http://localhost:8086"
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = None
        self.write_api = None
    
    def connect(self) -> bool:
        """Connect to InfluxDB."""
        try:
            # Lazy import - only if InfluxDB is installed
            from influxdb_client import InfluxDBClient
            from influxdb_client.client.write_api import SYNCHRONOUS
            
            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            return True
        except ImportError:
            logging.warning("influxdb-client not installed. Data will be logged only.")
            return False
        except Exception as e:
            logging.error(f"InfluxDB connection failed: {e}")
            return False
    
    def write(self, measurement: str, tags: Dict[str, str], fields: Dict[str, Any]) -> bool:
        """Write a data point to InfluxDB."""
        if not self.write_api:
            # Log to file instead
            logging.info(f"[MOCK_INFLUX] {measurement} tags={tags} fields={fields}")
            return True
        
        try:
            from influxdb_client import Point
            
            point = Point(measurement)
            for k, v in tags.items():
                point.tag(k, v)
            for k, v in fields.items():
                point.field(k, v)
            
            self.write_api.write(bucket=self.bucket, record=point)
            return True
        except Exception as e:
            logging.error(f"InfluxDB write failed: {e}")
            return False


# Global InfluxDB writer (initialized on first use)
_influx_writer = None

def get_influx_writer() -> InfluxDBWriter:
    """Get or create the global InfluxDB writer."""
    global _influx_writer
    if _influx_writer is None:
        import os
        _influx_writer = InfluxDBWriter(
            url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
            token=os.getenv("INFLUXDB_TOKEN"),
            org=os.getenv("INFLUXDB_ORG", "factorylm"),
            bucket=os.getenv("INFLUXDB_BUCKET", "sensors")
        )
        _influx_writer.connect()
    return _influx_writer
