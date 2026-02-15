"""
System Fingerprint Module
==========================

Tracks structural changes across the system:
- Configuration file hashes
- Service states
- Node reachability
- Environment variable presence
- System topology

Detects infrastructure changes that might affect system behavior.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class FingerprintReport:
    """System fingerprint comparison report."""
    timestamp: datetime
    current_fingerprint: str
    previous_fingerprint: Optional[str] = None
    changed: bool = False
    changes_detected: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if system structure changed."""
        return self.changed


class SystemFingerprint:
    """
    System structural fingerprinting.

    Tracks:
    - Config file hashes
    - Service availability
    - Node reachability
    - Environment variables
    """

    def __init__(self, config: dict, state_dir: str):
        """
        Initialize system fingerprinting.

        Args:
            config: Watchdog configuration
            state_dir: Directory to store fingerprint state
        """
        self.config = config
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.fingerprint_config = config.get("fingerprint", {})
        self.monitored_files = self.fingerprint_config.get("monitored_files", [])
        self.monitored_env_vars = self.fingerprint_config.get(
            "monitored_env_vars", []
        )

        self.fingerprint_file = self.state_dir / "system_fingerprint.json"

    def _hash_file(self, file_path: str) -> Optional[str]:
        """
        Compute hash of a file.

        Args:
            file_path: Path to file

        Returns:
            SHA256 hash or None if file doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            return None

        try:
            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()[:16]  # Shortened for compactness
        except Exception as e:
            logger.error(f"Error hashing {file_path}: {e}")
            return None

    def _get_file_hashes(self) -> Dict[str, Optional[str]]:
        """
        Get hashes of all monitored files.

        Returns:
            Dictionary mapping file path to hash
        """
        hashes = {}
        for file_path in self.monitored_files:
            hashes[file_path] = self._hash_file(file_path)
        return hashes

    def _get_env_var_status(self) -> Dict[str, bool]:
        """
        Check presence of monitored environment variables.

        Returns:
            Dictionary mapping var name to presence status
        """
        status = {}
        for var_name in self.monitored_env_vars:
            status[var_name] = os.getenv(var_name) is not None
        return status

    def _get_service_states(self) -> Dict[str, str]:
        """
        Get states of monitored services.

        Returns:
            Dictionary mapping service name to state
        """
        # This would integrate with health checker
        # For now, return placeholder
        services = self.config.get("health", {}).get("services", [])
        states = {}
        for svc in services:
            # Simplified - in production would check actual state
            states[svc["name"]] = "unknown"
        return states

    def _get_node_states(self) -> Dict[str, str]:
        """
        Get reachability of monitored nodes.

        Returns:
            Dictionary mapping node ID to reachability
        """
        # This would integrate with health checker
        # For now, return placeholder
        nodes = self.config.get("health", {}).get("nodes", [])
        states = {}
        for node in nodes:
            # Simplified - in production would check actual reachability
            states[node["id"]] = "unknown"
        return states

    def _compute_fingerprint(
        self,
        file_hashes: Dict[str, Optional[str]],
        env_vars: Dict[str, bool],
        service_states: Dict[str, str],
        node_states: Dict[str, str],
    ) -> str:
        """
        Compute overall system fingerprint.

        Args:
            file_hashes: File hash map
            env_vars: Environment variable presence map
            service_states: Service state map
            node_states: Node reachability map

        Returns:
            SHA256 fingerprint of system structure
        """
        fingerprint_data = {
            "files": file_hashes,
            "env_vars": env_vars,
            "services": service_states,
            "nodes": node_states,
        }

        # Create deterministic JSON representation
        json_str = json.dumps(fingerprint_data, sort_keys=True)

        # Hash the JSON
        hasher = hashlib.sha256()
        hasher.update(json_str.encode("utf-8"))

        return hasher.hexdigest()

    def _load_previous_fingerprint(self) -> Optional[dict]:
        """
        Load previously saved fingerprint.

        Returns:
            Previous fingerprint data or None
        """
        if not self.fingerprint_file.exists():
            return None

        try:
            with open(self.fingerprint_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading previous fingerprint: {e}")
            return None

    def _save_fingerprint(
        self,
        fingerprint: str,
        file_hashes: Dict[str, Optional[str]],
        env_vars: Dict[str, bool],
        service_states: Dict[str, str],
        node_states: Dict[str, str],
    ):
        """
        Save current fingerprint to disk.

        Args:
            fingerprint: System fingerprint hash
            file_hashes: File hash map
            env_vars: Environment variable map
            service_states: Service state map
            node_states: Node state map
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "fingerprint": fingerprint,
            "details": {
                "files": file_hashes,
                "env_vars": env_vars,
                "services": service_states,
                "nodes": node_states,
            },
        }

        try:
            with open(self.fingerprint_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("Saved system fingerprint")
        except Exception as e:
            logger.error(f"Error saving fingerprint: {e}")

    def _compare_fingerprints(
        self,
        previous: dict,
        current_file_hashes: Dict[str, Optional[str]],
        current_env_vars: Dict[str, bool],
        current_service_states: Dict[str, str],
        current_node_states: Dict[str, str],
    ) -> List[str]:
        """
        Compare current state to previous fingerprint.

        Args:
            previous: Previous fingerprint data
            current_file_hashes: Current file hashes
            current_env_vars: Current env var status
            current_service_states: Current service states
            current_node_states: Current node states

        Returns:
            List of detected changes
        """
        changes = []
        prev_details = previous.get("details", {})

        # Compare files
        prev_files = prev_details.get("files", {})
        for file_path, current_hash in current_file_hashes.items():
            prev_hash = prev_files.get(file_path)
            if prev_hash != current_hash:
                if prev_hash is None:
                    changes.append(f"New file: {file_path}")
                elif current_hash is None:
                    changes.append(f"Deleted file: {file_path}")
                else:
                    changes.append(f"Modified file: {file_path}")

        # Compare env vars
        prev_env = prev_details.get("env_vars", {})
        for var_name, current_present in current_env_vars.items():
            prev_present = prev_env.get(var_name, False)
            if prev_present != current_present:
                if current_present:
                    changes.append(f"Env var added: {var_name}")
                else:
                    changes.append(f"Env var removed: {var_name}")

        # Compare services
        prev_services = prev_details.get("services", {})
        for svc_name, current_state in current_service_states.items():
            prev_state = prev_services.get(svc_name)
            if prev_state != current_state:
                changes.append(
                    f"Service state changed: {svc_name} "
                    f"({prev_state} -> {current_state})"
                )

        # Compare nodes
        prev_nodes = prev_details.get("nodes", {})
        for node_id, current_state in current_node_states.items():
            prev_state = prev_nodes.get(node_id)
            if prev_state != current_state:
                changes.append(
                    f"Node state changed: {node_id} "
                    f"({prev_state} -> {current_state})"
                )

        return changes

    async def check_fingerprint(self) -> FingerprintReport:
        """
        Check system fingerprint for structural changes.

        Returns:
            Fingerprint comparison report
        """
        logger.info("Computing system fingerprint")

        # Gather current state
        file_hashes = self._get_file_hashes()
        env_vars = self._get_env_var_status()
        service_states = self._get_service_states()
        node_states = self._get_node_states()

        # Compute current fingerprint
        current_fingerprint = self._compute_fingerprint(
            file_hashes, env_vars, service_states, node_states
        )

        # Load previous fingerprint
        previous = self._load_previous_fingerprint()

        report = FingerprintReport(
            timestamp=datetime.now(),
            current_fingerprint=current_fingerprint,
        )

        if previous is None:
            # First run - establish baseline
            logger.info("Establishing baseline system fingerprint")
            self._save_fingerprint(
                current_fingerprint,
                file_hashes,
                env_vars,
                service_states,
                node_states,
            )
            return report

        previous_fingerprint = previous.get("fingerprint")
        report.previous_fingerprint = previous_fingerprint

        if current_fingerprint != previous_fingerprint:
            # Structural change detected
            logger.warning("System fingerprint changed - structural drift detected")
            report.changed = True

            # Identify specific changes
            report.changes_detected = self._compare_fingerprints(
                previous,
                file_hashes,
                env_vars,
                service_states,
                node_states,
            )

            for change in report.changes_detected:
                logger.info(f"  - {change}")

            # Save new fingerprint
            self._save_fingerprint(
                current_fingerprint,
                file_hashes,
                env_vars,
                service_states,
                node_states,
            )

        else:
            logger.info("System fingerprint unchanged")

        return report
