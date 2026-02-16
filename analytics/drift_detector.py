"""
Drift Detector - Celery Tasks
==============================
Detects when metrics drift from baseline and triggers alerts.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import json
from pathlib import Path

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking
from analytics.baseline_builder import builder as baseline_builder

# State storage
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)
DRIFT_LOG = STATE_DIR / "drift_log.jsonl"
DRIFT_STATE = STATE_DIR / "drift_state.json"

# Alert thresholds
DRIFT_THRESHOLD_SIGMA = float(os.getenv("DRIFT_THRESHOLD_SIGMA", "2.0"))
CRITICAL_THRESHOLD_SIGMA = float(os.getenv("CRITICAL_THRESHOLD_SIGMA", "3.0"))


class DriftDetector(BaseAgent):
    """Detects metric drift from baselines."""
    
    def __init__(self):
        super().__init__("DriftDetector")
        self._init_state()
    
    def _init_state(self):
        """Initialize drift state."""
        if not DRIFT_STATE.exists():
            state = {
                "checks_performed": 0,
                "drifts_detected": 0,
                "last_check": None,
                "active_alerts": [],
            }
            self._save_state(state)
    
    def _load_state(self) -> dict:
        with open(DRIFT_STATE, 'r') as f:
            return json.load(f)
    
    def _save_state(self, state: dict):
        with open(DRIFT_STATE, 'w') as f:
            json.dump(state, f, indent=2)
    
    def calculate_drift(self, current_value: float, baseline: Dict) -> Tuple[float, str]:
        """
        Calculate drift magnitude in standard deviations.
        
        Returns:
            (drift_sigma, severity)
        """
        mean = baseline["mean"]
        std_dev = baseline["std_dev"]
        
        if std_dev == 0:
            # No variance in baseline, use percentage from mean
            if mean == 0:
                return 0.0, "normal"
            drift = abs(current_value - mean) / abs(mean) * 100
            if drift > 20:
                return drift, "critical"
            elif drift > 10:
                return drift, "warning"
            return drift, "normal"
        
        drift_sigma = abs(current_value - mean) / std_dev
        
        if drift_sigma >= CRITICAL_THRESHOLD_SIGMA:
            return drift_sigma, "critical"
        elif drift_sigma >= DRIFT_THRESHOLD_SIGMA:
            return drift_sigma, "warning"
        return drift_sigma, "normal"
    
    def check_drift(self, metric_name: str, current_value: float,
                   vendor: str = None, plc_ip: str = None) -> Dict:
        """
        Check if a metric has drifted from baseline.
        
        Returns alert if drift detected, None otherwise.
        """
        # Get baseline
        baseline = baseline_builder.get_baseline(metric_name, vendor, plc_ip)
        
        if not baseline:
            return {
                "status": "no_baseline",
                "metric": metric_name,
                "message": "No baseline found for this metric"
            }
        
        # Calculate drift
        drift_sigma, severity = self.calculate_drift(current_value, baseline)
        
        result = {
            "metric": metric_name,
            "vendor": vendor,
            "plc_ip": plc_ip,
            "current_value": current_value,
            "baseline_mean": baseline["mean"],
            "baseline_std": baseline["std_dev"],
            "drift_sigma": round(drift_sigma, 2),
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Update state
        state = self._load_state()
        state["checks_performed"] += 1
        state["last_check"] = datetime.now().isoformat()
        
        if severity in ("warning", "critical"):
            state["drifts_detected"] += 1
            
            # Log drift event
            self._log_drift(result)
            
            # Add to active alerts (if not already there)
            alert_key = f"{metric_name}_{vendor}_{plc_ip}"
            if alert_key not in [a.get("key") for a in state["active_alerts"]]:
                state["active_alerts"].append({
                    "key": alert_key,
                    "metric": metric_name,
                    "severity": severity,
                    "detected_at": result["timestamp"],
                    "drift_sigma": drift_sigma,
                })
        
        self._save_state(state)
        
        return result
    
    def _log_drift(self, drift_event: Dict):
        """Log drift event to file."""
        with open(DRIFT_LOG, 'a') as f:
            f.write(json.dumps(drift_event) + '\n')
    
    def check_multiple(self, metrics: Dict[str, float], 
                      vendor: str = None, plc_ip: str = None) -> Dict:
        """
        Check multiple metrics at once.
        
        Args:
            metrics: Dict of metric_name -> current_value
            vendor: Optional PLC vendor
            plc_ip: Optional PLC IP
        
        Returns:
            Summary with any drift alerts
        """
        results = []
        alerts = []
        
        for metric_name, value in metrics.items():
            result = self.check_drift(metric_name, value, vendor, plc_ip)
            results.append(result)
            
            if result.get("severity") in ("warning", "critical"):
                alerts.append(result)
        
        return {
            "checked": len(results),
            "alerts": len(alerts),
            "alert_details": alerts,
            "timestamp": datetime.now().isoformat(),
        }
    
    def get_active_alerts(self) -> List[Dict]:
        """Get list of active drift alerts."""
        state = self._load_state()
        return state.get("active_alerts", [])
    
    def clear_alert(self, metric_name: str, vendor: str = None, plc_ip: str = None) -> bool:
        """Clear an active alert (e.g., after resolution)."""
        state = self._load_state()
        alert_key = f"{metric_name}_{vendor}_{plc_ip}"
        
        original_len = len(state["active_alerts"])
        state["active_alerts"] = [
            a for a in state["active_alerts"] if a.get("key") != alert_key
        ]
        
        self._save_state(state)
        return len(state["active_alerts"]) < original_len
    
    def get_stats(self) -> Dict:
        """Get drift detection statistics."""
        state = self._load_state()
        return {
            "checks_performed": state.get("checks_performed", 0),
            "drifts_detected": state.get("drifts_detected", 0),
            "active_alerts": len(state.get("active_alerts", [])),
            "last_check": state.get("last_check"),
        }


detector = DriftDetector()


@app.task(bind=True, name='drift.check')
@with_token_tracking('drift')
def check(self, metric_name: str, current_value: float,
          vendor: str = None, plc_ip: str = None) -> Dict:
    """
    Check if a metric has drifted from baseline.
    
    Args:
        metric_name: Name of the metric
        current_value: Current metric value
        vendor: Optional PLC vendor
        plc_ip: Optional PLC IP
    
    Returns:
        Drift status with severity
    """
    detector.log_start('check', metric_name=metric_name, value=current_value)
    result = detector.check_drift(metric_name, current_value, vendor, plc_ip)
    detector.log_complete('check', result)
    return result


@app.task(bind=True, name='drift.check_multiple')
@with_token_tracking('drift')
def check_multiple(self, metrics: Dict[str, float],
                  vendor: str = None, plc_ip: str = None) -> Dict:
    """
    Check multiple metrics at once.
    
    Args:
        metrics: Dict of metric_name -> current_value
    """
    detector.log_start('check_multiple', metrics=len(metrics))
    result = detector.check_multiple(metrics, vendor, plc_ip)
    detector.log_complete('check_multiple', result)
    
    # If alerts detected, create work order + trigger workflows + generate report
    if result["alerts"] > 0:
        from workers.conductor_tasks import handle_drift_alert
        from integrations.telegram_alerts import send_drift_alert
        from integrations.postgres_cmms import create_drift_work_order
        from workers.weaver_tasks import generate_drift_report
        
        for alert in result["alert_details"]:
            # Create work order in Postgres (reliable, no external deps)
            wo_result = create_drift_work_order(alert)
            if wo_result.get("wo_number"):
                alert["work_order"] = wo_result["wo_number"]
            
            # Generate report (syncs to all devices via Syncthing)
            generate_drift_report.delay(alert)
            
            # Trigger agent workflow
            handle_drift_alert.delay(
                sensor=alert["metric"],
                magnitude=alert["drift_sigma"],
                plc_vendor=alert.get("vendor", "unknown"),
                related_metrics=list(metrics.keys())
            )
            # Send Telegram alert
            send_drift_alert(alert)
    
    return result


@app.task(bind=True, name='drift.get_alerts')
def get_alerts(self) -> List[Dict]:
    """Get active drift alerts."""
    return detector.get_active_alerts()


@app.task(bind=True, name='drift.clear_alert')
def clear_alert(self, metric_name: str, vendor: str = None, plc_ip: str = None) -> Dict:
    """Clear a resolved drift alert."""
    success = detector.clear_alert(metric_name, vendor, plc_ip)
    return {"cleared": success, "metric": metric_name}


@app.task(bind=True, name='drift.stats')
def stats(self) -> Dict:
    """Get drift detection statistics."""
    return detector.get_stats()


@app.task(bind=True, name='drift.health')
def health(self) -> Dict:
    """Health check."""
    s = detector.get_stats()
    return {
        "status": "ok",
        "agent": "DriftDetector",
        "active_alerts": s["active_alerts"],
        "checks_performed": s["checks_performed"]
    }
