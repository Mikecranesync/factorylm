"""
State Management for PEPPER

Snapshot and restore session state, routing tables, and runtime configuration.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib


class StateManager:
    """Manage PEPPER runtime state for deployment and rollback"""

    def __init__(self, pepper_home: Path):
        """
        Initialize state manager

        Args:
            pepper_home: Path to PEPPER home directory
        """
        self.pepper_home = Path(pepper_home)
        self.state_dir = self.pepper_home / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def snapshot_state(self, version_dir: Path) -> Dict[str, Any]:
        """
        Create complete state snapshot for deployment

        Args:
            version_dir: Directory to save state snapshot

        Returns:
            State snapshot dictionary
        """
        state_snapshot = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'sessions': self._snapshot_sessions(),
            'routing': self._snapshot_routing(),
            'config': self._snapshot_config(),
            'metrics': self._snapshot_metrics(),
        }

        # Save snapshot to version directory
        snapshot_dir = version_dir / "state"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        snapshot_path = snapshot_dir / "snapshot.json"
        with open(snapshot_path, 'w') as f:
            json.dump(state_snapshot, f, indent=2)

        # Calculate snapshot hash
        state_snapshot['hash'] = self._calculate_hash(state_snapshot)

        return state_snapshot

    def restore_state(self, version_dir: Path) -> bool:
        """
        Restore state from snapshot

        Args:
            version_dir: Directory containing state snapshot

        Returns:
            True if restore successful, False otherwise
        """
        snapshot_path = version_dir / "state" / "snapshot.json"

        if not snapshot_path.exists():
            print(f"No state snapshot found at {snapshot_path}")
            return False

        try:
            with open(snapshot_path, 'r') as f:
                state_snapshot = json.load(f)

            # Restore components
            self._restore_sessions(state_snapshot.get('sessions', {}))
            self._restore_routing(state_snapshot.get('routing', {}))
            self._restore_config(state_snapshot.get('config', {}))
            self._restore_metrics(state_snapshot.get('metrics', {}))

            print(f"State restored from {state_snapshot['timestamp']}")
            return True

        except Exception as e:
            print(f"Error restoring state: {e}")
            return False

    def _snapshot_sessions(self) -> Dict[str, Any]:
        """
        Snapshot active user sessions

        Returns:
            Sessions state dictionary
        """
        sessions_file = self.state_dir / "sessions.json"

        if not sessions_file.exists():
            return {'active_sessions': {}, 'session_count': 0}

        try:
            with open(sessions_file, 'r') as f:
                sessions = json.load(f)
            return sessions
        except Exception as e:
            print(f"Warning: Could not snapshot sessions: {e}")
            return {'active_sessions': {}, 'session_count': 0}

    def _restore_sessions(self, sessions_state: Dict[str, Any]):
        """Restore user sessions"""
        sessions_file = self.state_dir / "sessions.json"

        try:
            with open(sessions_file, 'w') as f:
                json.dump(sessions_state, f, indent=2)
            print(f"Restored {sessions_state.get('session_count', 0)} sessions")
        except Exception as e:
            print(f"Warning: Could not restore sessions: {e}")

    def _snapshot_routing(self) -> Dict[str, Any]:
        """
        Snapshot routing table and twin mappings

        Returns:
            Routing state dictionary
        """
        routing_file = self.state_dir / "routing.json"

        if not routing_file.exists():
            return {
                'routing_table': {},
                'twin_mappings': {},
                'active_routes': 0
            }

        try:
            with open(routing_file, 'r') as f:
                routing = json.load(f)
            return routing
        except Exception as e:
            print(f"Warning: Could not snapshot routing: {e}")
            return {
                'routing_table': {},
                'twin_mappings': {},
                'active_routes': 0
            }

    def _restore_routing(self, routing_state: Dict[str, Any]):
        """Restore routing table"""
        routing_file = self.state_dir / "routing.json"

        try:
            with open(routing_file, 'w') as f:
                json.dump(routing_state, f, indent=2)
            print(f"Restored {routing_state.get('active_routes', 0)} routes")
        except Exception as e:
            print(f"Warning: Could not restore routing: {e}")

    def _snapshot_config(self) -> Dict[str, Any]:
        """
        Snapshot runtime configuration

        Returns:
            Config state dictionary
        """
        config_file = self.state_dir / "runtime_config.json"

        if not config_file.exists():
            return {'runtime_config': {}}

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            print(f"Warning: Could not snapshot config: {e}")
            return {'runtime_config': {}}

    def _restore_config(self, config_state: Dict[str, Any]):
        """Restore runtime configuration"""
        config_file = self.state_dir / "runtime_config.json"

        try:
            with open(config_file, 'w') as f:
                json.dump(config_state, f, indent=2)
            print("Restored runtime configuration")
        except Exception as e:
            print(f"Warning: Could not restore config: {e}")

    def _snapshot_metrics(self) -> Dict[str, Any]:
        """
        Snapshot metrics and counters

        Returns:
            Metrics state dictionary
        """
        metrics_file = self.state_dir / "metrics.json"

        if not metrics_file.exists():
            return {
                'message_count': 0,
                'error_count': 0,
                'uptime_seconds': 0
            }

        try:
            with open(metrics_file, 'r') as f:
                metrics = json.load(f)
            return metrics
        except Exception as e:
            print(f"Warning: Could not snapshot metrics: {e}")
            return {
                'message_count': 0,
                'error_count': 0,
                'uptime_seconds': 0
            }

    def _restore_metrics(self, metrics_state: Dict[str, Any]):
        """Restore metrics"""
        metrics_file = self.state_dir / "metrics.json"

        try:
            with open(metrics_file, 'w') as f:
                json.dump(metrics_state, f, indent=2)
            print("Restored metrics")
        except Exception as e:
            print(f"Warning: Could not restore metrics: {e}")

    def _calculate_hash(self, data: Dict[str, Any]) -> str:
        """
        Calculate SHA256 hash of state data

        Args:
            data: State data dictionary

        Returns:
            Hex digest of hash
        """
        # Remove hash field if present
        data_copy = data.copy()
        data_copy.pop('hash', None)

        # Convert to JSON string and hash
        json_str = json.dumps(data_copy, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def validate_state(self, version_dir: Path) -> bool:
        """
        Validate state snapshot integrity

        Args:
            version_dir: Directory containing state snapshot

        Returns:
            True if valid, False otherwise
        """
        snapshot_path = version_dir / "state" / "snapshot.json"

        if not snapshot_path.exists():
            return False

        try:
            with open(snapshot_path, 'r') as f:
                state_snapshot = json.load(f)

            stored_hash = state_snapshot.get('hash')
            if not stored_hash:
                return False

            # Recalculate hash
            calculated_hash = self._calculate_hash(state_snapshot)

            return stored_hash == calculated_hash

        except Exception as e:
            print(f"Error validating state: {e}")
            return False

    def export_state(self, output_path: Path):
        """
        Export current state for backup

        Args:
            output_path: Path to export state to
        """
        state_snapshot = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'sessions': self._snapshot_sessions(),
            'routing': self._snapshot_routing(),
            'config': self._snapshot_config(),
            'metrics': self._snapshot_metrics(),
        }

        state_snapshot['hash'] = self._calculate_hash(state_snapshot)

        with open(output_path, 'w') as f:
            json.dump(state_snapshot, f, indent=2)

        print(f"State exported to {output_path}")

    def import_state(self, input_path: Path) -> bool:
        """
        Import state from backup

        Args:
            input_path: Path to import state from

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(input_path, 'r') as f:
                state_snapshot = json.load(f)

            # Validate hash
            stored_hash = state_snapshot.get('hash')
            calculated_hash = self._calculate_hash(state_snapshot)

            if stored_hash != calculated_hash:
                print("Error: State file integrity check failed")
                return False

            # Restore components
            self._restore_sessions(state_snapshot.get('sessions', {}))
            self._restore_routing(state_snapshot.get('routing', {}))
            self._restore_config(state_snapshot.get('config', {}))
            self._restore_metrics(state_snapshot.get('metrics', {}))

            print(f"State imported from {input_path}")
            return True

        except Exception as e:
            print(f"Error importing state: {e}")
            return False
