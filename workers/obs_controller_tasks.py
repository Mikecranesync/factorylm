"""
OBS CONTROLLER - Camera Switching via WebSocket
================================================
Controls OBS Studio on PLC laptop via WebSocket API.

Requires on PLC laptop:
1. OBS Studio with WebSocket plugin (v5+)
2. obsws-python: pip install obsws-python
3. WebSocket server enabled on port 4455

Architecture:
- VPS sends commands via Tailscale (100.72.2.99:4455)
- OBS executes scene/source switches
- Returns confirmation
"""

import os
import sys
import json
import socket
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_celery_tracing

logger = logging.getLogger(__name__)

# OBS WebSocket config
OBS_HOST = os.getenv('OBS_HOST', '100.72.2.99')  # PLC Laptop Tailscale IP
OBS_PORT = int(os.getenv('OBS_PORT', '4455'))
OBS_PASSWORD = os.getenv('OBS_PASSWORD', 'factorylm_demo')

# Camera ID to OBS Scene mapping
CAMERA_SCENE_MAP = {
    'CAM-1': 'Factory_IO_Overview',
    'CAM-2': 'Factory_IO_Closeup', 
    'CAM-3': 'PLC_Physical',
    'CAM-4': 'PLC_IO_LEDs',
    'CAM-5': 'Code_Editor',
    'CAM-6': 'Mermaid_Diagram',
    'CAM-7': 'Presenter_Wide',
    'CAM-8': 'Presenter_Close',
    'CAM-9': 'Phone_Demo',
    'CAM-10': 'Terminal',
    'CAM-11': 'Network_Traffic',
    'CAM-12': 'Browser_UI',
    'CAM-13': 'Split_Sim_PLC',
    'CAM-14': 'Outro',
}


class OBSController(BaseAgent):
    """
    Controls OBS via WebSocket.
    
    Uses obsws-python for clean API access.
    Falls back to raw WebSocket if library unavailable.
    """
    
    def __init__(self):
        super().__init__("OBSController")
        self._client = None
        self._connected = False
    
    def _ensure_connected(self) -> bool:
        """Ensure we have a connection to OBS."""
        if self._connected and self._client:
            return True
        
        try:
            # Try obsws-python first
            import obsws_python as obs
            self._client = obs.ReqClient(
                host=OBS_HOST,
                port=OBS_PORT,
                password=OBS_PASSWORD,
                timeout=5
            )
            self._connected = True
            self.logger.info(f"Connected to OBS at {OBS_HOST}:{OBS_PORT}")
            return True
            
        except ImportError:
            self.logger.warning("obsws-python not installed, using raw WebSocket")
            return self._connect_raw_websocket()
            
        except Exception as e:
            self.logger.error(f"Failed to connect to OBS: {e}")
            self._connected = False
            return False
    
    def _connect_raw_websocket(self) -> bool:
        """Fallback: connect via raw websocket."""
        try:
            import websocket
            ws_url = f"ws://{OBS_HOST}:{OBS_PORT}"
            self._client = websocket.create_connection(ws_url, timeout=5)
            self._connected = True
            return True
        except Exception as e:
            self.logger.error(f"Raw WebSocket connection failed: {e}")
            return False
    
    def switch_scene(self, scene_name: str) -> dict:
        """
        Switch to a named scene.
        
        Args:
            scene_name: OBS scene name (e.g., 'Factory_IO_Overview')
        """
        if not self._ensure_connected():
            return {"error": "Not connected to OBS", "scene": scene_name}
        
        try:
            if hasattr(self._client, 'set_current_program_scene'):
                # obsws-python client
                self._client.set_current_program_scene(scene_name)
                return {"success": True, "scene": scene_name}
            else:
                # Raw websocket
                msg = json.dumps({
                    "op": 6,
                    "d": {
                        "requestType": "SetCurrentProgramScene",
                        "requestData": {"sceneName": scene_name}
                    }
                })
                self._client.send(msg)
                return {"success": True, "scene": scene_name, "method": "raw"}
                
        except Exception as e:
            self.logger.error(f"Scene switch failed: {e}")
            return {"error": str(e), "scene": scene_name}
    
    def switch_to_camera(self, camera_id: str) -> dict:
        """
        Switch to a camera by ID (CAM-1 through CAM-14).
        
        Maps camera ID to OBS scene name.
        """
        scene_name = CAMERA_SCENE_MAP.get(camera_id)
        if not scene_name:
            return {"error": f"Unknown camera: {camera_id}"}
        
        result = self.switch_scene(scene_name)
        result['camera_id'] = camera_id
        return result
    
    def get_current_scene(self) -> dict:
        """Get the current active scene."""
        if not self._ensure_connected():
            return {"error": "Not connected to OBS"}
        
        try:
            if hasattr(self._client, 'get_current_program_scene'):
                resp = self._client.get_current_program_scene()
                return {"scene": resp.current_program_scene_name}
            else:
                return {"error": "Method not available in raw mode"}
        except Exception as e:
            return {"error": str(e)}
    
    def list_scenes(self) -> dict:
        """List all available scenes."""
        if not self._ensure_connected():
            return {"error": "Not connected to OBS"}
        
        try:
            if hasattr(self._client, 'get_scene_list'):
                resp = self._client.get_scene_list()
                scenes = [s['sceneName'] for s in resp.scenes]
                return {"scenes": scenes, "current": resp.current_program_scene_name}
            else:
                return {"error": "Method not available in raw mode"}
        except Exception as e:
            return {"error": str(e)}
    
    def set_source_visibility(self, scene: str, source: str, visible: bool) -> dict:
        """Show/hide a source within a scene."""
        if not self._ensure_connected():
            return {"error": "Not connected to OBS"}
        
        try:
            if hasattr(self._client, 'set_scene_item_enabled'):
                # Need to get item ID first
                items = self._client.get_scene_item_list(scene)
                for item in items.scene_items:
                    if item.get('sourceName') == source:
                        self._client.set_scene_item_enabled(
                            scene,
                            item['sceneItemId'],
                            visible
                        )
                        return {"success": True, "source": source, "visible": visible}
                return {"error": f"Source '{source}' not found in scene '{scene}'"}
            else:
                return {"error": "Method not available in raw mode"}
        except Exception as e:
            return {"error": str(e)}
    
    def start_recording(self) -> dict:
        """Start OBS recording."""
        if not self._ensure_connected():
            return {"error": "Not connected to OBS"}
        
        try:
            if hasattr(self._client, 'start_record'):
                self._client.start_record()
                return {"success": True, "action": "recording_started"}
            else:
                return {"error": "Method not available"}
        except Exception as e:
            return {"error": str(e)}
    
    def stop_recording(self) -> dict:
        """Stop OBS recording."""
        if not self._ensure_connected():
            return {"error": "Not connected to OBS"}
        
        try:
            if hasattr(self._client, 'stop_record'):
                resp = self._client.stop_record()
                return {"success": True, "output_path": getattr(resp, 'output_path', 'unknown')}
            else:
                return {"error": "Method not available"}
        except Exception as e:
            return {"error": str(e)}
    
    def test_connection(self) -> dict:
        """Test OBS connection."""
        # First check if port is even reachable
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((OBS_HOST, OBS_PORT))
            sock.close()
            
            if result != 0:
                return {
                    "connected": False,
                    "error": f"Cannot reach {OBS_HOST}:{OBS_PORT}",
                    "suggestion": "Ensure OBS is running with WebSocket enabled on PLC laptop"
                }
        except Exception as e:
            return {"connected": False, "error": str(e)}
        
        # Port is reachable, try actual connection
        if self._ensure_connected():
            return {
                "connected": True,
                "host": OBS_HOST,
                "port": OBS_PORT,
                "scenes": self.list_scenes()
            }
        else:
            return {"connected": False, "error": "Connection failed after socket success"}


# Singleton
_controller = None

def get_controller() -> OBSController:
    global _controller
    if _controller is None:
        _controller = OBSController()
    return _controller


# =============================================================================
# CELERY TASKS
# =============================================================================

@app.task(bind=True, name='obs.switch_scene')
@with_celery_tracing
def switch_scene(self, scene_name: str) -> dict:
    """
    Switch OBS to a named scene.
    
    Usage: celery call obs.switch_scene --args='["Factory_IO_Overview"]'
    """
    return get_controller().switch_scene(scene_name)


@app.task(bind=True, name='obs.switch_camera')
@with_celery_tracing
def switch_to_camera(self, camera_id: str) -> dict:
    """
    Switch to camera by ID (CAM-1 through CAM-14).
    
    Usage: celery call obs.switch_camera --args='["CAM-3"]'
    """
    return get_controller().switch_to_camera(camera_id)


@app.task(bind=True, name='obs.current')
@with_celery_tracing
def get_current_scene(self) -> dict:
    """Get current OBS scene."""
    return get_controller().get_current_scene()


@app.task(bind=True, name='obs.list')
@with_celery_tracing
def list_scenes(self) -> dict:
    """List all OBS scenes."""
    return get_controller().list_scenes()


@app.task(bind=True, name='obs.visibility')
@with_celery_tracing
def set_visibility(self, scene: str, source: str, visible: bool) -> dict:
    """Set source visibility within a scene."""
    return get_controller().set_source_visibility(scene, source, visible)


@app.task(bind=True, name='obs.record_start')
@with_celery_tracing
def start_recording(self) -> dict:
    """Start OBS recording (for fallback video capture)."""
    return get_controller().start_recording()


@app.task(bind=True, name='obs.record_stop')
@with_celery_tracing
def stop_recording(self) -> dict:
    """Stop OBS recording."""
    return get_controller().stop_recording()


@app.task(bind=True, name='obs.test')
@with_celery_tracing
def test_connection(self) -> dict:
    """Test OBS WebSocket connection."""
    return get_controller().test_connection()


# =============================================================================
# SCENE TRANSITION SEQUENCES
# =============================================================================

@app.task(bind=True, name='obs.transition_sequence')
@with_celery_tracing
def run_transition_sequence(self, sequence: List[Dict]) -> dict:
    """
    Run a sequence of timed transitions.
    
    sequence: [
        {"scene": "CAM-1", "duration": 5},
        {"scene": "CAM-3", "duration": 10},
        ...
    ]
    """
    import time
    controller = get_controller()
    results = []
    
    for step in sequence:
        scene = step.get('scene')
        duration = step.get('duration', 5)
        
        result = controller.switch_to_camera(scene)
        results.append({
            "scene": scene,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        if duration > 0:
            time.sleep(duration)
    
    return {"sequence_complete": True, "steps": results}


if __name__ == "__main__":
    # Test connection
    controller = get_controller()
    result = controller.test_connection()
    print(json.dumps(result, indent=2))
