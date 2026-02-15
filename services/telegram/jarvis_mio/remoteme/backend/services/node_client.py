"""
Node Client Service
===================
Communicate with Jarvis Node agents running on remote computers.
"""

import logging
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from langfuse import observe

from backend.config import settings

logger = logging.getLogger(__name__)


def get_node_url(node_name: str) -> str:
    """Get base URL for a node"""
    node = settings.NODES.get(node_name)
    if not node:
        raise ValueError(f"Unknown node: {node_name}")
    return f"http://{node['ip']}:{node['port']}"


@observe(name="execute_on_node")
async def execute_on_node(
    node_name: str,
    intent: str,
    args: Dict[str, Any],
    timeout: int = 60
) -> Dict[str, Any]:
    """
    Execute command on a remote node.
    
    Args:
        node_name: Name of the target node
        intent: Command intent (screenshot, shell, interpret, etc.)
        args: Arguments for the command
        timeout: Request timeout in seconds
        
    Returns:
        Execution result with output, screenshots, etc.
    """
    
    base_url = get_node_url(node_name)
    logger.info(f"Executing {intent} on {node_name} ({base_url})")
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if intent == "screenshot":
                return await _execute_screenshot(client, base_url, args)
            
            elif intent == "shell":
                return await _execute_shell(client, base_url, args)
            
            elif intent == "interpret":
                return await _execute_interpret(client, base_url, args)
            
            elif intent == "click":
                return await _execute_click(client, base_url, args)
            
            elif intent == "type":
                return await _execute_type(client, base_url, args)
            
            elif intent == "keypress":
                return await _execute_keypress(client, base_url, args)
            
            else:
                return {"error": f"Unknown intent: {intent}"}
                
        except httpx.ConnectError:
            logger.error(f"Cannot connect to {node_name} at {base_url}")
            return {"error": f"Cannot connect to {node_name}. Is it online?"}
        except httpx.TimeoutException:
            logger.error(f"Timeout connecting to {node_name}")
            return {"error": f"Timeout waiting for {node_name}"}
        except Exception as e:
            logger.error(f"Node execution error: {e}")
            return {"error": str(e)}


async def _execute_screenshot(client: httpx.AsyncClient, base_url: str, args: Dict) -> Dict:
    """Take screenshot"""
    monitor = args.get("monitor", 0)
    response = await client.get(f"{base_url}/screenshot", params={"monitor": monitor})
    response.raise_for_status()
    data = response.json()
    
    # Save screenshot locally
    if data.get("image_base64"):
        screenshot_path = settings.UPLOAD_DIR / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        img_data = base64.b64decode(data["image_base64"])
        screenshot_path.write_bytes(img_data)
        data["screenshot_path"] = str(screenshot_path)
    
    data["output"] = f"Screenshot captured ({data.get('size', ['?', '?'])[0]}x{data.get('size', ['?', '?'])[1]})"
    return data


async def _execute_shell(client: httpx.AsyncClient, base_url: str, args: Dict) -> Dict:
    """Run shell command"""
    command = args.get("command", "")
    timeout = args.get("timeout", 30)
    
    response = await client.post(f"{base_url}/shell", json={
        "command": command,
        "timeout": timeout
    })
    response.raise_for_status()
    data = response.json()
    
    output = data.get("stdout", "")
    if data.get("stderr"):
        output += f"\n\nErrors:\n{data['stderr']}"
    
    data["output"] = output or "(no output)"
    return data


async def _execute_interpret(client: httpx.AsyncClient, base_url: str, args: Dict) -> Dict:
    """Execute via Open Interpreter"""
    instruction = args.get("instruction", "")
    model = args.get("model", "ollama/llama3.2:latest")
    
    response = await client.post(f"{base_url}/interpret", json={
        "command": instruction,
        "model": model,
        "auto_run": True
    }, timeout=120)  # Longer timeout for interpreter
    response.raise_for_status()
    data = response.json()
    
    return data


async def _execute_click(client: httpx.AsyncClient, base_url: str, args: Dict) -> Dict:
    """Click at coordinates"""
    response = await client.post(f"{base_url}/click", json={
        "x": args.get("x", 0),
        "y": args.get("y", 0),
        "button": args.get("button", "left"),
        "clicks": args.get("clicks", 1)
    })
    response.raise_for_status()
    data = response.json()
    data["output"] = f"Clicked at ({args.get('x')}, {args.get('y')})"
    return data


async def _execute_type(client: httpx.AsyncClient, base_url: str, args: Dict) -> Dict:
    """Type text"""
    response = await client.post(f"{base_url}/type", json={
        "text": args.get("text", "")
    })
    response.raise_for_status()
    data = response.json()
    data["output"] = f"Typed: {args.get('text', '')}"
    return data


async def _execute_keypress(client: httpx.AsyncClient, base_url: str, args: Dict) -> Dict:
    """Press key combination"""
    key = args.get("key", "")
    response = await client.post(f"{base_url}/keypress", params={"key": key})
    response.raise_for_status()
    data = response.json()
    data["output"] = f"Pressed: {key}"
    return data


async def check_node_health(node_name: str) -> Dict[str, Any]:
    """Check if a node is online and healthy"""
    try:
        base_url = get_node_url(node_name)
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{base_url}/health")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"status": "offline", "error": str(e)}
