"""WebSocket endpoint for real-time I/O updates."""

import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.plc_connection import plc_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Active WebSocket connections
active_connections: Set[WebSocket] = set()


async def broadcast_io_data():
    """Broadcast current I/O data to all connected clients."""
    if not plc_service.is_connected:
        return

    try:
        io_data = plc_service.read_io()
        message = json.dumps(io_data)

        # Send to all active connections
        disconnected = set()
        for connection in active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)

        # Remove disconnected clients
        active_connections.difference_update(disconnected)
    except Exception as e:
        logger.debug(f"I/O read for broadcast failed: {e}")


@router.websocket("/ws/io")
async def websocket_io(websocket: WebSocket):
    """
    WebSocket endpoint for real-time I/O updates.

    Pushes I/O data to connected clients every 100ms when there's an
    active PLC connection.
    """
    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"WebSocket connected. Active connections: {len(active_connections)}")

    try:
        while True:
            # Poll PLC every 100ms and push data
            if plc_service.is_connected:
                try:
                    io_data = plc_service.read_io()
                    await websocket.send_json(io_data)
                except Exception as e:
                    # Send error status on read failure
                    await websocket.send_json({
                        "error": str(e),
                        "connected": False
                    })

            await asyncio.sleep(0.1)  # 100ms polling interval

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        active_connections.discard(websocket)
        logger.info(f"WebSocket removed. Active connections: {len(active_connections)}")
