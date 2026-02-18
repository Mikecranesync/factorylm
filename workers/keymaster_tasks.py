"""
Keymaster Agent - API Key Guardian
===================================
Crawls codebase looking for:
1. Missing keys (referenced but not set)
2. Invalid/expired keys
3. Exposed keys in code (security risk)
4. Key health checks (test API endpoints)

Runs every 30 minutes, explores different sections each run.
"""

import os
import sys
import re
import json
import time
import glob
import hashlib
from datetime import datetime
from typing import Dict, List, Set, Optional
from pathlib import Path
import requests
import logging

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking

logger = logging.getLogger(__name__)

# Key patterns to search for
KEY_PATTERNS = {
    "groq": r"gsk_[a-zA-Z0-9]{20,}",
    "openai": r"sk-[a-zA-Z0-9]{20,}",
    "anthropic": r"sk-ant-[a-zA-Z0-9\-]{20,}",
    "gemini": r"AIzaSy[a-zA-Z0-9\-_]{33}",
    "github": r"ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{22,}",
    "aws_access": r"AKIA[0-9A-Z]{16}",
    "aws_secret": r"[a-zA-Z0-9/+]{40}",
    "stripe": r"sk_live_[a-zA-Z0-9]{24,}|sk_test_[a-zA-Z0-9]{24,}",
    "telegram": r"\d{9,10}:[a-zA-Z0-9_-]{35}",
    "langfuse": r"sk-lf-[a-zA-Z0-9\-]{36}|pk-lf-[a-zA-Z0-9\-]{36}",
    "trello": r"ATTA[a-zA-Z0-9]{60,}",
    "perplexity": r"pplx-[a-zA-Z0-9]{48}",
}

# Environment variable references to check
ENV_VAR_REFS = [
    "GROQ_API_KEY",
    "OPENAI_API_KEY", 
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GITHUB_TOKEN",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "STRIPE_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "TRELLO_API_KEY",
    "TRELLO_TOKEN",
    "PERPLEXITY_API_KEY",
    "JIRA_API_TOKEN",
    "FLOWISE_API_KEY",
]

# Directories to scan
SCAN_DIRS = [
    "/root/jarvis-workspace",
    "/opt/master_of_puppets",
    "/opt/factorylm-sync",
]

# Files to skip
SKIP_PATTERNS = [
    "*.pyc", "__pycache__", ".git", "node_modules",
    "*.log", "*.jsonl", "venv", ".venv", "*.egg-info"
]

# State file to track exploration progress
STATE_FILE = "/opt/master_of_puppets/state/keymaster_state.json"


class KeymasterAgent(BaseAgent):
    """Guardian of API keys across the codebase."""
    
    def __init__(self):
        super().__init__("Keymaster")
        self.state = self._load_state()
        self.alerts: List[Dict] = []
        self.found_keys: Dict[str, List[Dict]] = {}
        self.missing_keys: List[str] = []
        self.exposed_keys: List[Dict] = []
        
    def _load_state(self) -> Dict:
        """Load exploration state."""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE) as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load state: {e}")
        
        return {
            "last_run": None,
            "explored_dirs": [],
            "exploration_index": 0,
            "known_keys_hash": {},
            "alerts_sent": []
        }
    
    def _save_state(self):
        """Save exploration state."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
    
    def _should_skip(self, path: str) -> bool:
        """Check if path should be skipped."""
        path_lower = path.lower()
        for pattern in SKIP_PATTERNS:
            if pattern.startswith("*"):
                if path_lower.endswith(pattern[1:]):
                    return True
            elif pattern in path_lower:
                return True
        return False
    
    def _get_next_exploration_section(self) -> str:
        """Get next directory section to explore."""
        all_dirs = []
        
        for base_dir in SCAN_DIRS:
            if os.path.exists(base_dir):
                for root, dirs, files in os.walk(base_dir):
                    # Filter out skip dirs
                    dirs[:] = [d for d in dirs if not self._should_skip(d)]
                    if files:  # Only add dirs with files
                        all_dirs.append(root)
        
        if not all_dirs:
            return SCAN_DIRS[0]
        
        # Rotate through directories
        idx = self.state.get("exploration_index", 0) % len(all_dirs)
        self.state["exploration_index"] = idx + 1
        return all_dirs[idx]
    
    def scan_for_exposed_keys(self, directory: str) -> List[Dict]:
        """Scan directory for exposed API keys in code."""
        exposed = []
        
        try:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if not self._should_skip(d)]
                
                for filename in files:
                    if self._should_skip(filename):
                        continue
                    
                    # Only scan text files
                    if not filename.endswith(('.py', '.js', '.ts', '.json', '.yaml', '.yml', '.md', '.txt', '.sh', '.env')):
                        continue
                    
                    filepath = os.path.join(root, filename)
                    
                    try:
                        with open(filepath, 'r', errors='ignore') as f:
                            content = f.read()
                        
                        for key_type, pattern in KEY_PATTERNS.items():
                            matches = re.findall(pattern, content)
                            for match in matches:
                                # Skip if it's in an example file
                                if '.example' in filename or 'example' in filepath.lower():
                                    continue
                                
                                # Skip if it's a placeholder
                                if 'your_' in match.lower() or 'xxx' in match.lower():
                                    continue
                                
                                # Check if this is a real exposure (not in .env)
                                if not filename.endswith('.env'):
                                    exposed.append({
                                        "type": key_type,
                                        "file": filepath,
                                        "key_preview": match[:10] + "..." + match[-4:],
                                        "severity": "HIGH" if key_type in ["aws_secret", "stripe", "anthropic"] else "MEDIUM"
                                    })
                                else:
                                    # Track found keys in .env files
                                    if key_type not in self.found_keys:
                                        self.found_keys[key_type] = []
                                    self.found_keys[key_type].append({
                                        "file": filepath,
                                        "key_hash": hashlib.sha256(match.encode()).hexdigest()[:16]
                                    })
                                    
                    except Exception as e:
                        pass  # Skip unreadable files
                        
        except Exception as e:
            self.logger.error(f"Scan error in {directory}: {e}")
        
        return exposed
    
    def check_missing_keys(self) -> List[str]:
        """Check for referenced but unset environment variables."""
        missing = []
        
        for var in ENV_VAR_REFS:
            value = os.environ.get(var, "")
            if not value or value.lower() in ["", "none", "null", "your_key", "xxx"]:
                # Check if it's referenced anywhere in the codebase
                for scan_dir in SCAN_DIRS:
                    if os.path.exists(scan_dir):
                        result = os.popen(f'grep -r "{var}" {scan_dir} --include="*.py" --include="*.env" 2>/dev/null | head -1').read()
                        if result.strip():
                            missing.append(var)
                            break
        
        return list(set(missing))
    
    def test_key_health(self) -> Dict[str, Dict]:
        """Test if keys are valid by making API calls."""
        health = {}
        
        # Test Groq
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key and groq_key.startswith("gsk_"):
            try:
                resp = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    timeout=10
                )
                health["groq"] = {"status": "ok" if resp.ok else "invalid", "code": resp.status_code}
            except Exception as e:
                health["groq"] = {"status": "error", "error": str(e)}
        
        # Test Gemini
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if gemini_key and gemini_key.startswith("AIzaSy"):
            try:
                resp = requests.get(
                    f"https://generativelanguage.googleapis.com/v1/models?key={gemini_key}",
                    timeout=10
                )
                health["gemini"] = {"status": "ok" if resp.ok else "invalid", "code": resp.status_code}
            except Exception as e:
                health["gemini"] = {"status": "error", "error": str(e)}
        
        # Test Perplexity
        pplx_key = os.environ.get("PERPLEXITY_API_KEY", "")
        if pplx_key and pplx_key.startswith("pplx-"):
            try:
                resp = requests.get(
                    "https://api.perplexity.ai/models",
                    headers={"Authorization": f"Bearer {pplx_key}"},
                    timeout=10
                )
                health["perplexity"] = {"status": "ok" if resp.ok else "invalid", "code": resp.status_code}
            except Exception as e:
                health["perplexity"] = {"status": "error", "error": str(e)}
        
        # Test LangFuse
        lf_secret = os.environ.get("LANGFUSE_SECRET_KEY", "")
        lf_public = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        if lf_secret and lf_public:
            health["langfuse"] = {"status": "configured", "has_secret": bool(lf_secret), "has_public": bool(lf_public)}
        
        return health
    
    def send_alert(self, alert_type: str, message: str, severity: str = "MEDIUM"):
        """Queue an alert to be sent."""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.alerts.append(alert)
        
        # Don't duplicate alerts
        alert_hash = hashlib.md5(f"{alert_type}:{message}".encode()).hexdigest()
        if alert_hash not in self.state.get("alerts_sent", []):
            self.state.setdefault("alerts_sent", []).append(alert_hash)
            # Keep only last 100 alerts
            self.state["alerts_sent"] = self.state["alerts_sent"][-100:]
    
    def run_scan(self, full_scan: bool = False) -> Dict:
        """Run a key scan."""
        self.logger.info("Starting Keymaster scan...")
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "scan_type": "full" if full_scan else "incremental",
            "exposed_keys": [],
            "missing_keys": [],
            "key_health": {},
            "found_keys": {},
            "alerts": [],
            "section_scanned": None
        }
        
        # Get section to scan
        if full_scan:
            sections = SCAN_DIRS
        else:
            section = self._get_next_exploration_section()
            sections = [section]
            results["section_scanned"] = section
        
        # Scan for exposed keys
        for section in sections:
            exposed = self.scan_for_exposed_keys(section)
            results["exposed_keys"].extend(exposed)
            
            for exp in exposed:
                self.send_alert(
                    "EXPOSED_KEY",
                    f"🚨 {exp['type']} key exposed in {exp['file']}",
                    exp["severity"]
                )
        
        # Check missing keys
        results["missing_keys"] = self.check_missing_keys()
        for missing in results["missing_keys"]:
            self.send_alert(
                "MISSING_KEY",
                f"⚠️ {missing} is referenced but not set",
                "MEDIUM"
            )
        
        # Test key health
        results["key_health"] = self.test_key_health()
        for key_name, status in results["key_health"].items():
            if status.get("status") == "invalid":
                self.send_alert(
                    "INVALID_KEY",
                    f"❌ {key_name} key is invalid (HTTP {status.get('code')})",
                    "HIGH"
                )
            elif status.get("status") == "error":
                self.send_alert(
                    "KEY_ERROR",
                    f"⚠️ {key_name} key check failed: {status.get('error')}",
                    "MEDIUM"
                )
        
        results["found_keys"] = {k: len(v) for k, v in self.found_keys.items()}
        results["alerts"] = self.alerts
        
        # Update state
        self.state["last_run"] = datetime.utcnow().isoformat()
        self._save_state()
        
        return results
    
    def get_key_inventory(self) -> Dict:
        """Get inventory of all configured keys."""
        inventory = {}
        
        for var in ENV_VAR_REFS:
            value = os.environ.get(var, "")
            if value and value.lower() not in ["", "none", "null"]:
                # Mask the key
                if len(value) > 8:
                    masked = value[:4] + "*" * (len(value) - 8) + value[-4:]
                else:
                    masked = "****"
                inventory[var] = {"status": "set", "preview": masked}
            else:
                inventory[var] = {"status": "missing", "preview": None}
        
        return inventory


keymaster = KeymasterAgent()


@app.task(bind=True, name='keymaster.scan')
@with_token_tracking('keymaster')
def scan(self, full_scan: bool = False) -> Dict:
    """Run a Keymaster scan."""
    keymaster.log_start('scan', full=full_scan)
    result = keymaster.run_scan(full_scan)
    keymaster.log_complete('scan', {"alerts": len(result["alerts"])})
    return result


@app.task(bind=True, name='keymaster.inventory')
def inventory(self) -> Dict:
    """Get key inventory."""
    return keymaster.get_key_inventory()


@app.task(bind=True, name='keymaster.test_health')
def test_health(self) -> Dict:
    """Test all key health."""
    return keymaster.test_key_health()


@app.task(bind=True, name='keymaster.health')
def health(self) -> Dict:
    """Health check."""
    return {
        "status": "ok",
        "agent": "Keymaster",
        "last_run": keymaster.state.get("last_run"),
        "exploration_index": keymaster.state.get("exploration_index", 0)
    }
