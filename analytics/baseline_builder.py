"""
Baseline Builder - Celery Tasks
================================
Calculates normal baselines from historical data.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
from pathlib import Path
import statistics

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking

# Database config
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "rivet"),
    "user": os.getenv("POSTGRES_USER", "rivet"),
    "password": os.getenv("POSTGRES_PASSWORD", "rivet_factory_2025!"),
}

# State storage
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)
BASELINES_FILE = STATE_DIR / "baselines.json"


class BaselineBuilder(BaseAgent):
    """Calculates and stores metric baselines."""
    
    def __init__(self):
        super().__init__("BaselineBuilder")
        self.conn = None
        self._ensure_table()
    
    def _get_connection(self):
        """Get database connection."""
        if self.conn is None or self.conn.closed:
            try:
                import psycopg2
                self.conn = psycopg2.connect(**DB_CONFIG)
            except Exception as e:
                self.logger.error(f"DB connection failed: {e}")
                return None
        return self.conn
    
    def _ensure_table(self):
        """Create baselines table if needed."""
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS metric_baselines (
                    id SERIAL PRIMARY KEY,
                    metric_name VARCHAR(100) NOT NULL,
                    vendor VARCHAR(50),
                    plc_ip VARCHAR(50),
                    mean FLOAT NOT NULL,
                    std_dev FLOAT NOT NULL,
                    min_val FLOAT,
                    max_val FLOAT,
                    p95 FLOAT,
                    p99 FLOAT,
                    sample_count INTEGER,
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_start TIMESTAMP,
                    data_end TIMESTAMP,
                    UNIQUE(metric_name, vendor, plc_ip)
                )
            """)
            conn.commit()
            cur.close()
        except Exception as e:
            self.logger.warning(f"Table creation: {e}")
            conn.rollback()
    
    def calculate_baseline(self, metric_name: str, values: List[float],
                          vendor: str = None, plc_ip: str = None) -> Dict:
        """Calculate baseline statistics from values."""
        if not values or len(values) < 10:
            return {"error": "Insufficient data (need at least 10 samples)"}
        
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        
        baseline = {
            "metric_name": metric_name,
            "vendor": vendor,
            "plc_ip": plc_ip,
            "mean": statistics.mean(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            "min_val": min(values),
            "max_val": max(values),
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[int(n * 0.99)],
            "sample_count": n,
            "calculated_at": datetime.now().isoformat(),
        }
        
        return baseline
    
    def store_baseline(self, baseline: Dict) -> bool:
        """Store baseline in database."""
        conn = self._get_connection()
        if not conn:
            # Fallback to file
            self._store_to_file(baseline)
            return True
        
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO metric_baselines 
                (metric_name, vendor, plc_ip, mean, std_dev, min_val, max_val, p95, p99, sample_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (metric_name, vendor, plc_ip) 
                DO UPDATE SET 
                    mean = EXCLUDED.mean,
                    std_dev = EXCLUDED.std_dev,
                    min_val = EXCLUDED.min_val,
                    max_val = EXCLUDED.max_val,
                    p95 = EXCLUDED.p95,
                    p99 = EXCLUDED.p99,
                    sample_count = EXCLUDED.sample_count,
                    calculated_at = CURRENT_TIMESTAMP
            """, (
                baseline["metric_name"], baseline.get("vendor"), baseline.get("plc_ip"),
                baseline["mean"], baseline["std_dev"], baseline["min_val"],
                baseline["max_val"], baseline["p95"], baseline["p99"],
                baseline["sample_count"]
            ))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            self.logger.error(f"Store baseline failed: {e}")
            conn.rollback()
            return False
    
    def _store_to_file(self, baseline: Dict):
        """Fallback: store to JSON file."""
        baselines = {}
        if BASELINES_FILE.exists():
            with open(BASELINES_FILE) as f:
                baselines = json.load(f)
        
        key = f"{baseline['metric_name']}_{baseline.get('vendor', '')}_{baseline.get('plc_ip', '')}"
        baselines[key] = baseline
        
        with open(BASELINES_FILE, 'w') as f:
            json.dump(baselines, f, indent=2)
    
    def get_baseline(self, metric_name: str, vendor: str = None, plc_ip: str = None) -> Optional[Dict]:
        """Retrieve a stored baseline."""
        conn = self._get_connection()
        if not conn:
            return self._get_from_file(metric_name, vendor, plc_ip)
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT metric_name, vendor, plc_ip, mean, std_dev, min_val, max_val, 
                       p95, p99, sample_count, calculated_at
                FROM metric_baselines
                WHERE metric_name = %s 
                  AND (vendor = %s OR %s IS NULL)
                  AND (plc_ip = %s OR %s IS NULL)
            """, (metric_name, vendor, vendor, plc_ip, plc_ip))
            
            row = cur.fetchone()
            cur.close()
            
            if row:
                return {
                    "metric_name": row[0],
                    "vendor": row[1],
                    "plc_ip": row[2],
                    "mean": row[3],
                    "std_dev": row[4],
                    "min_val": row[5],
                    "max_val": row[6],
                    "p95": row[7],
                    "p99": row[8],
                    "sample_count": row[9],
                    "calculated_at": row[10].isoformat() if row[10] else None,
                }
            return None
        except Exception as e:
            self.logger.error(f"Get baseline failed: {e}")
            return None
    
    def _get_from_file(self, metric_name: str, vendor: str = None, plc_ip: str = None) -> Optional[Dict]:
        """Fallback: get from file."""
        if not BASELINES_FILE.exists():
            return None
        
        with open(BASELINES_FILE) as f:
            baselines = json.load(f)
        
        key = f"{metric_name}_{vendor or ''}_{plc_ip or ''}"
        return baselines.get(key)
    
    def list_baselines(self) -> List[Dict]:
        """List all stored baselines."""
        conn = self._get_connection()
        if not conn:
            return []
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT metric_name, vendor, plc_ip, mean, std_dev, sample_count, calculated_at
                FROM metric_baselines
                ORDER BY calculated_at DESC
            """)
            
            results = []
            for row in cur.fetchall():
                results.append({
                    "metric_name": row[0],
                    "vendor": row[1],
                    "plc_ip": row[2],
                    "mean": row[3],
                    "std_dev": row[4],
                    "sample_count": row[5],
                    "calculated_at": row[6].isoformat() if row[6] else None,
                })
            cur.close()
            return results
        except Exception as e:
            self.logger.error(f"List baselines failed: {e}")
            return []


builder = BaselineBuilder()


@app.task(bind=True, name='baseline.calculate')
@with_token_tracking('baseline')
def calculate(self, metric_name: str, values: List[float], 
              vendor: str = None, plc_ip: str = None) -> Dict:
    """
    Calculate baseline statistics for a metric.
    
    Args:
        metric_name: Name of the metric (e.g., "motor_speed")
        values: List of historical values
        vendor: Optional PLC vendor
        plc_ip: Optional PLC IP address
    
    Returns:
        Baseline statistics (mean, std_dev, percentiles)
    """
    builder.log_start('calculate', metric_name=metric_name, samples=len(values))
    
    baseline = builder.calculate_baseline(metric_name, values, vendor, plc_ip)
    
    if "error" not in baseline:
        builder.store_baseline(baseline)
        builder.log_complete('calculate', baseline)
    
    return baseline


@app.task(bind=True, name='baseline.get')
def get(self, metric_name: str, vendor: str = None, plc_ip: str = None) -> Dict:
    """Get stored baseline for a metric."""
    baseline = builder.get_baseline(metric_name, vendor, plc_ip)
    return baseline or {"error": "Baseline not found"}


@app.task(bind=True, name='baseline.list')
def list_all(self) -> List[Dict]:
    """List all stored baselines."""
    return builder.list_baselines()


@app.task(bind=True, name='baseline.health')
def health(self) -> Dict:
    """Health check."""
    baselines = builder.list_baselines()
    return {
        "status": "ok",
        "agent": "BaselineBuilder",
        "baselines_stored": len(baselines)
    }
