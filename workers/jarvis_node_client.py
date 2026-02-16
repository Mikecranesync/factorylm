"""
Jarvis Node Client - Call remote Windows laptops from VPS
=========================================================
Used by Clawdbot to control Windows laptops via Telegram
"""

import requests
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# Node registry
NODES = {
    "plc-laptop": {
        "ip": "100.72.2.99",
        "port": 8765,
        "type": "windows",
        "description": "PLC Laptop - Quadro P620, Ollama, RSLogix"
    },
    "travel-laptop": {
        "ip": "100.83.251.23", 
        "port": 8765,
        "type": "windows",
        "description": "Travel Laptop - Development, presentations"
    },
    "raspberry-pi": {
        "ip": None,  # Set when Pi joins Tailscale
        "port": 8765,
        "type": "linux",
        "description": "Raspberry Pi - Camera, GPIO, sensors"
    }
}


class JarvisNodeClient:
    """Client for calling Jarvis Node endpoints"""
    
    def __init__(self, node_name: str):
        if node_name not in NODES:
            raise ValueError(f"Unknown node: {node_name}. Available: {list(NODES.keys())}")
        
        self.node = NODES[node_name]
        self.base_url = f"http://{self.node['ip']}:{self.node['port']}"
        self.name = node_name
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to node"""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("timeout", 30)
        
        try:
            resp = requests.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"error": f"Cannot connect to {self.name} at {url}"}
        except requests.exceptions.Timeout:
            return {"error": f"Timeout connecting to {self.name}"}
        except Exception as e:
            return {"error": str(e)}
    
    def health(self) -> Dict[str, Any]:
        """Check node health"""
        return self._request("GET", "/health")
    
    def shell(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Run shell command"""
        return self._request("POST", "/shell", json={"command": command, "timeout": timeout})
    
    def screenshot(self, monitor: int = 0, save_path: Optional[str] = None) -> Dict[str, Any]:
        """Take screenshot, optionally save to file"""
        result = self._request("GET", f"/screenshot?monitor={monitor}")
        
        if save_path and "image_base64" in result:
            img_data = base64.b64decode(result["image_base64"])
            Path(save_path).write_bytes(img_data)
            result["saved_to"] = save_path
        
        return result
    
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
        """Click at position"""
        return self._request("POST", "/click", json={
            "x": x, "y": y, "button": button, "clicks": clicks
        })
    
    def type_text(self, text: str) -> Dict[str, Any]:
        """Type text"""
        return self._request("POST", "/type", json={"text": text})
    
    def keypress(self, key: str) -> Dict[str, Any]:
        """Press key or key combo (e.g. 'ctrl+s')"""
        return self._request("POST", f"/keypress?key={key}")
    
    def camera(self, device: int = 0, save_path: Optional[str] = None) -> Dict[str, Any]:
        """Capture from camera"""
        result = self._request("GET", f"/camera?device={device}")
        
        if save_path and "image_base64" in result:
            img_data = base64.b64decode(result["image_base64"])
            Path(save_path).write_bytes(img_data)
            result["saved_to"] = save_path
        
        return result
    
    def clipboard(self, action: str, content: Optional[str] = None) -> Dict[str, Any]:
        """Read/write clipboard. action = 'copy' or 'paste'"""
        return self._request("POST", "/clipboard", json={
            "action": action, "content": content
        })
    
    def file_read(self, path: str) -> Dict[str, Any]:
        """Read file from node"""
        return self._request("POST", "/file/read", json={"path": path})
    
    def file_write(self, path: str, content: str) -> Dict[str, Any]:
        """Write file to node"""
        return self._request("POST", "/file/write", json={"path": path, "content": content})
    
    def file_list(self, path: str) -> Dict[str, Any]:
        """List directory on node"""
        return self._request("POST", "/file/list", json={"path": path})
    
    def processes(self) -> Dict[str, Any]:
        """List running processes"""
        return self._request("GET", "/processes")
    
    def interpret(self, command: str, model: str = "ollama/llama3.2:latest", auto_run: bool = True) -> Dict[str, Any]:
        """
        Execute natural language command via Open Interpreter.
        
        Args:
            command: Natural language instruction (e.g. "open chrome and go to google.com")
            model: LLM model to use (default: local ollama)
            auto_run: Auto-execute commands without confirmation
        
        Returns:
            Result with output from interpreter
        """
        return self._request("POST", "/interpret", json={
            "command": command,
            "model": model,
            "auto_run": auto_run
        }, timeout=120)  # Longer timeout for complex tasks


# Convenience functions
def plc_laptop() -> JarvisNodeClient:
    """Get PLC laptop client"""
    return JarvisNodeClient("plc-laptop")

def travel_laptop() -> JarvisNodeClient:
    """Get travel laptop client"""
    return JarvisNodeClient("travel-laptop")

def all_nodes_health() -> Dict[str, Any]:
    """Check health of all nodes"""
    results = {}
    for name in NODES:
        client = JarvisNodeClient(name)
        results[name] = client.health()
    return results


# Quick test
if __name__ == "__main__":
    print("🔍 Checking all nodes...")
    for name, status in all_nodes_health().items():
        if "error" in status:
            print(f"  ❌ {name}: {status['error']}")
        else:
            print(f"  ✅ {name}: {status.get('status', 'unknown')}")
