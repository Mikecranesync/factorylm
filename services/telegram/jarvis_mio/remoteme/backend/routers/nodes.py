"""
Nodes Router
============
API endpoints for managing remote computer nodes.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import get_db, Node
from backend.services.node_client import check_node_health, get_node_url

router = APIRouter()


class NodeStatus(BaseModel):
    """Node status response"""
    name: str
    ip: str
    port: int
    status: str
    capabilities: Optional[dict] = None
    error: Optional[str] = None


@router.get("/", response_model=List[NodeStatus])
async def list_nodes():
    """List all configured nodes with their status"""
    results = []
    
    for name, config in settings.NODES.items():
        health = await check_node_health(name)
        
        results.append(NodeStatus(
            name=name,
            ip=config["ip"],
            port=config["port"],
            status=health.get("status", "unknown"),
            capabilities=health.get("capabilities"),
            error=health.get("error")
        ))
    
    return results


@router.get("/{node_name}")
async def get_node_status(node_name: str):
    """Get detailed status of a specific node"""
    if node_name not in settings.NODES:
        raise HTTPException(404, f"Node '{node_name}' not found")
    
    config = settings.NODES[node_name]
    health = await check_node_health(node_name)
    
    return {
        "name": node_name,
        "config": config,
        "health": health,
        "url": get_node_url(node_name)
    }


@router.post("/{node_name}/screenshot")
async def take_screenshot(node_name: str, monitor: int = 0):
    """Take screenshot from a node"""
    from backend.services.node_client import execute_on_node
    
    result = await execute_on_node(
        node_name=node_name,
        intent="screenshot",
        args={"monitor": monitor}
    )
    
    if result.get("error"):
        raise HTTPException(500, result["error"])
    
    return result


@router.post("/{node_name}/shell")
async def run_shell_command(node_name: str, command: str, timeout: int = 30):
    """Run shell command on a node"""
    from backend.services.node_client import execute_on_node
    
    result = await execute_on_node(
        node_name=node_name,
        intent="shell",
        args={"command": command, "timeout": timeout}
    )
    
    if result.get("error"):
        raise HTTPException(500, result["error"])
    
    return result


@router.post("/{node_name}/interpret")
async def interpret_command(node_name: str, instruction: str):
    """Execute natural language command via Open Interpreter"""
    from backend.services.node_client import execute_on_node
    
    result = await execute_on_node(
        node_name=node_name,
        intent="interpret",
        args={"instruction": instruction}
    )
    
    if result.get("error"):
        raise HTTPException(500, result["error"])
    
    return result
