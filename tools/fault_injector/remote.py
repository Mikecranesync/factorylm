"""
Remote Control Module
=====================
Functions to control the PLC laptop remotely via SSH and Jarvis Node.
"""

import subprocess
import httpx
import time
import logging
from typing import Optional, Dict, Any

from .config import (
    SSH_USER, SSH_HOST, JARVIS_NODE,
    FACTORY_IO_EXE, FACTORY_IO_SCENES, DEFAULT_SCENE
)

logger = logging.getLogger(__name__)
http = httpx.Client(timeout=30)


# ============================================================================
# SSH Commands
# ============================================================================

def ssh_command(cmd: str, timeout: int = 30) -> tuple[int, str, str]:
    """
    Execute a command on PLC laptop via SSH.

    Args:
        cmd: Command to execute
        timeout: Timeout in seconds

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    full_cmd = f'ssh {SSH_USER}@{SSH_HOST} "{cmd}"'
    logger.debug(f"SSH: {cmd}")

    try:
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


def ssh_powershell(script: str, timeout: int = 30) -> tuple[int, str, str]:
    """
    Execute PowerShell script on PLC laptop via SSH.

    Args:
        script: PowerShell script to execute
        timeout: Timeout in seconds

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    # Escape for SSH
    escaped = script.replace('"', '\\"').replace("'", "\\'")
    cmd = f"powershell -Command \"{escaped}\""
    return ssh_command(cmd, timeout)


# ============================================================================
# Jarvis Node API
# ============================================================================

def jarvis_health() -> Dict[str, Any]:
    """Check Jarvis node health."""
    try:
        resp = http.get(f"{JARVIS_NODE}/health")
        return resp.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


def jarvis_shell(command: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Execute shell command via Jarvis node.

    Args:
        command: Command to execute
        timeout: Timeout in seconds

    Returns:
        Response dict with stdout, stderr, return_code
    """
    try:
        resp = http.post(
            f"{JARVIS_NODE}/shell",
            json={"command": command, "timeout": timeout}
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e), "return_code": -1}


# ============================================================================
# Factory I/O Control
# ============================================================================

def is_factory_io_running() -> bool:
    """Check if Factory I/O is running on PLC laptop."""
    result = jarvis_shell('tasklist | findstr "Factory"')
    stdout = result.get("stdout", "")
    return "Factory IO.exe" in stdout


def start_factory_io(scene: Optional[str] = None) -> bool:
    """
    Start Factory I/O on PLC laptop.

    Args:
        scene: Optional scene file to load (defaults to DEFAULT_SCENE)

    Returns:
        bool: True if started successfully
    """
    if is_factory_io_running():
        logger.info("Factory I/O already running")
        return True

    scene = scene or DEFAULT_SCENE
    scene_path = f"{FACTORY_IO_SCENES}\\{scene}.factoryio"

    # Start Factory I/O with scene
    cmd = f'Start-Process "{FACTORY_IO_EXE}" -ArgumentList \'"{scene_path}"\''
    result = jarvis_shell(f'powershell -Command "{cmd}"')

    if result.get("return_code", -1) != 0:
        logger.error(f"Failed to start Factory I/O: {result}")
        return False

    # Wait for startup
    logger.info("Waiting for Factory I/O to start...")
    for _ in range(30):  # 30 second timeout
        time.sleep(1)
        if is_factory_io_running():
            logger.info("Factory I/O started successfully")
            return True

    logger.error("Factory I/O failed to start within timeout")
    return False


def stop_factory_io() -> bool:
    """Stop Factory I/O on PLC laptop."""
    result = jarvis_shell('taskkill /IM "Factory IO.exe" /F')
    return result.get("return_code", -1) == 0


def get_factory_io_status() -> Dict[str, Any]:
    """Get Factory I/O status including Modbus connectivity."""
    status = {
        "running": is_factory_io_running(),
        "jarvis": jarvis_health(),
    }

    # Check Modbus port
    result = jarvis_shell('netstat -an | findstr ":502"')
    status["modbus_listening"] = ":502" in result.get("stdout", "")

    return status
