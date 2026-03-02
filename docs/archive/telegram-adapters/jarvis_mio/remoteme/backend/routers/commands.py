"""
Commands Router
===============
API endpoints for command management.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.database import get_db, Command
from backend.services.command_parser import parse_command
from backend.services.node_client import execute_on_node

router = APIRouter()


class CommandRequest(BaseModel):
    """Request to execute a command"""
    text: str
    node: Optional[str] = "plc-laptop"


class CommandResponse(BaseModel):
    """Command execution response"""
    id: Optional[int] = None
    status: str
    intent: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    execution_time_ms: Optional[int] = None


@router.post("/execute", response_model=CommandResponse)
async def execute_command(request: CommandRequest, db: Session = Depends(get_db)):
    """
    Execute a natural language command.
    
    This endpoint:
    1. Parses the command with Claude
    2. Executes on the target node
    3. Returns the result
    """
    start_time = datetime.utcnow()
    
    # Parse command
    parsed = await parse_command(request.text)
    
    if parsed.get("intent") == "unknown":
        return CommandResponse(
            status="error",
            error=f"Could not understand command: {parsed.get('reason', 'Unknown error')}"
        )
    
    # Override node if specified
    node = request.node or parsed.get("node", "plc-laptop")
    
    # Execute
    result = await execute_on_node(
        node_name=node,
        intent=parsed["intent"],
        args=parsed.get("args", {})
    )
    
    # Calculate execution time
    execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    
    # Check for errors
    if result.get("error"):
        return CommandResponse(
            status="error",
            intent=parsed["intent"],
            error=result["error"],
            execution_time_ms=execution_time
        )
    
    return CommandResponse(
        status="completed",
        intent=parsed["intent"],
        output=result.get("output", "Done"),
        screenshot_path=result.get("screenshot_path"),
        execution_time_ms=execution_time
    )


@router.get("/history")
async def get_command_history(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get command history"""
    commands = db.query(Command).order_by(Command.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "commands": [
            {
                "id": c.id,
                "raw_text": c.raw_text,
                "intent": c.parsed_intent,
                "status": c.status,
                "output": c.output[:200] if c.output else None,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in commands
        ],
        "limit": limit,
        "offset": offset
    }
