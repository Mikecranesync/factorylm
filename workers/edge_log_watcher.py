"""
EDGE LOG WATCHER - Celery Tasks
================================
Watches for new log files from edge devices (BeagleBone, etc.)
and ingests them into InfluxDB for time-series analysis.
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking, with_celery_tracing
from observability import traced, track_llm_call, track_api_call

# Paths
EDGE_LOGS_DIR = Path("/opt/factorylm-sync/edge-logs")
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)
WATCHER_STATE = STATE_DIR / "edge_log_watcher_state.json"

# InfluxDB config
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "factorylm-influx-token-2026")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "factorylm")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensors")


class EdgeLogWatcher(BaseAgent):
    """Watches edge device logs and ingests to InfluxDB."""
    
    def __init__(self):
        super().__init__("EdgeLogWatcher")
        self._init_state()
        self._influx_client = None
    
    def _init_state(self):
        if not WATCHER_STATE.exists():
            state = {
                "processed_files": {},  # filepath -> last_position
                "total_lines_ingested": 0,
                "last_scan": None,
                "devices": {},  # device_name -> stats
            }
            self._save_state(state)
    
    def _load_state(self) -> Dict:
        try:
            with open(WATCHER_STATE, 'r') as f:
                return json.load(f)
        except:
            self._init_state()
            return self._load_state()
    
    def _save_state(self, state: Dict):
        with open(WATCHER_STATE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    def _get_influx_client(self):
        """Get InfluxDB client."""
        if self._influx_client is None:
            try:
                from influxdb_client import InfluxDBClient
                self._influx_client = InfluxDBClient(
                    url=INFLUXDB_URL,
                    token=INFLUXDB_TOKEN,
                    org=INFLUXDB_ORG
                )
            except ImportError:
                self.logger.error("influxdb-client not installed")
                return None
            except Exception as e:
                self.logger.error(f"InfluxDB connection failed: {e}")
                return None
        return self._influx_client
    
    def parse_modbus_log_line(self, line: str, device: str) -> Optional[Dict]:
        """
        Parse a Modbus log line into InfluxDB point data.
        
        Expected formats:
        - "2026-02-01T10:30:00,register_40001,123.45"
        - "2026-02-01 10:30:00 | addr:40001 | value:123.45"
        - JSON: {"timestamp": "...", "register": 40001, "value": 123.45}
        """
        line = line.strip()
        if not line:
            return None
        
        try:
            # Try JSON first
            if line.startswith('{'):
                data = json.loads(line)
                return {
                    "measurement": "modbus_data",
                    "tags": {
                        "device": device,
                        "register": str(data.get("register", data.get("addr", "unknown"))),
                    },
                    "fields": {
                        "value": float(data.get("value", 0)),
                    },
                    "time": data.get("timestamp", datetime.now().isoformat()),
                }
            
            # Try CSV format: timestamp,register,value
            if ',' in line:
                parts = line.split(',')
                if len(parts) >= 3:
                    return {
                        "measurement": "modbus_data",
                        "tags": {
                            "device": device,
                            "register": parts[1].strip(),
                        },
                        "fields": {
                            "value": float(parts[2].strip()),
                        },
                        "time": parts[0].strip(),
                    }
            
            # Try pipe-delimited format
            if '|' in line:
                # Extract values using regex
                addr_match = re.search(r'addr[:\s]*(\d+)', line, re.IGNORECASE)
                val_match = re.search(r'value[:\s]*([\d.]+)', line, re.IGNORECASE)
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})', line)
                
                if addr_match and val_match:
                    return {
                        "measurement": "modbus_data",
                        "tags": {
                            "device": device,
                            "register": addr_match.group(1),
                        },
                        "fields": {
                            "value": float(val_match.group(1)),
                        },
                        "time": time_match.group(1) if time_match else datetime.now().isoformat(),
                    }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Failed to parse line: {line[:50]}... - {e}")
            return None
    
    def ingest_log_file(self, filepath: Path, device: str) -> Dict:
        """
        Ingest a log file into InfluxDB.
        Tracks position to only process new lines.
        """
        state = self._load_state()
        file_key = str(filepath)
        last_position = state["processed_files"].get(file_key, 0)
        
        client = self._get_influx_client()
        if not client:
            return {"error": "InfluxDB client not available"}
        
        try:
            from influxdb_client import Point
            from influxdb_client.client.write_api import SYNCHRONOUS
            
            write_api = client.write_api(write_options=SYNCHRONOUS)
            
            lines_processed = 0
            points_written = 0
            
            with open(filepath, 'r') as f:
                # Seek to last known position
                f.seek(last_position)
                
                for line in f:
                    lines_processed += 1
                    
                    parsed = self.parse_modbus_log_line(line, device)
                    if parsed:
                        point = Point(parsed["measurement"])
                        for tag_key, tag_val in parsed["tags"].items():
                            point = point.tag(tag_key, tag_val)
                        for field_key, field_val in parsed["fields"].items():
                            point = point.field(field_key, field_val)
                        
                        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                        points_written += 1
                
                # Save new position
                new_position = f.tell()
            
            # Update state
            state["processed_files"][file_key] = new_position
            state["total_lines_ingested"] += points_written
            if device not in state["devices"]:
                state["devices"][device] = {"files_processed": 0, "lines_ingested": 0}
            state["devices"][device]["files_processed"] += 1
            state["devices"][device]["lines_ingested"] += points_written
            self._save_state(state)
            
            return {
                "file": filepath.name,
                "device": device,
                "lines_processed": lines_processed,
                "points_written": points_written,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to ingest {filepath}: {e}")
            return {"error": str(e), "file": filepath.name}
    
    def scan_edge_logs(self) -> Dict:
        """Scan all edge device log folders for new data."""
        state = self._load_state()
        state["last_scan"] = datetime.now().isoformat()
        
        results = []
        
        # Scan each device folder
        for device_folder in EDGE_LOGS_DIR.iterdir():
            if device_folder.is_dir():
                device_name = device_folder.name
                
                # Process all .log files
                for logfile in device_folder.glob("*.log"):
                    result = self.ingest_log_file(logfile, device_name)
                    results.append(result)
        
        self._save_state(state)
        
        return {
            "devices_scanned": len([d for d in EDGE_LOGS_DIR.iterdir() if d.is_dir()]),
            "files_processed": len(results),
            "results": results,
            "total_lines_ingested": state["total_lines_ingested"],
        }
    
    def get_stats(self) -> Dict:
        state = self._load_state()
        return {
            "total_lines_ingested": state.get("total_lines_ingested", 0),
            "last_scan": state.get("last_scan"),
            "devices": state.get("devices", {}),
            "files_tracked": len(state.get("processed_files", {})),
        }


watcher = EdgeLogWatcher()


# ============== CELERY TASKS ==============

@app.task(bind=True, name='edge_watcher.scan_logs')
@with_token_tracking('edge_watcher')
def scan_logs(self) -> Dict:
    """
    Scan edge device logs and ingest to InfluxDB.
    Called by Celery Beat every 1 minute.
    """
    watcher.log_start('scan_logs')
    result = watcher.scan_edge_logs()
    watcher.log_complete('scan_logs', result)
    return result


@app.task(bind=True, name='edge_watcher.ingest_file')
@with_token_tracking('edge_watcher')
def ingest_file(self, filepath: str, device: str) -> Dict:
    """Ingest a specific log file."""
    watcher.log_start('ingest_file', file=filepath)
    result = watcher.ingest_log_file(Path(filepath), device)
    watcher.log_complete('ingest_file', result)
    return result


@app.task(bind=True, name='edge_watcher.stats')
@with_celery_tracing("stats")
@traced(name="stats", layer="execution")
def stats(self) -> Dict:
    """Get watcher statistics."""
    return watcher.get_stats()


@app.task(bind=True, name='edge_watcher.health')
@with_celery_tracing("health")
@traced(name="health", layer="execution")
def health(self) -> Dict:
    """Health check."""
    client = watcher._get_influx_client()
    return {
        "status": "ok" if client else "influxdb_unavailable",
        "edge_logs_dir_exists": EDGE_LOGS_DIR.exists(),
        "devices_found": len([d for d in EDGE_LOGS_DIR.iterdir() if d.is_dir()]) if EDGE_LOGS_DIR.exists() else 0,
    }
