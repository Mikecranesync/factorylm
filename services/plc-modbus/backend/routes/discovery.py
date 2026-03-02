"""SSE stream and REST endpoints for auto-discovered PLC devices."""

import asyncio
import json
import logging
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.services.discovery_daemon import discovery_daemon

logger = logging.getLogger(__name__)

router = APIRouter(tags=["discovery"])

# Max chars per SSE data: line to avoid browser silent truncation
_SSE_CHUNK_SIZE = 1000


@router.get("/devices")
async def list_devices():
    """List all discovered EtherNet/IP devices."""
    devices = []
    for ip, dev in discovery_daemon.devices.items():
        devices.append({
            "ip": dev.ip,
            "port": dev.port,
            "status": dev.status,
            "product": dev.plc_info.get("product_name", ""),
            "tag_count": len(dev.tag_list),
            "first_seen": dev.first_seen.isoformat(),
            "last_seen": dev.last_seen.isoformat(),
        })
    return {
        "devices": devices,
        "subnet": discovery_daemon._subnet,
        "scan_interval_s": settings.discovery_scan_interval,
    }


@router.get("/devices/{ip}/tags")
async def device_tags(ip: str):
    """Get the latest tags for a specific device."""
    dev = discovery_daemon.devices.get(ip)
    if dev is None:
        return {"error": "Device not found", "ip": ip}
    return {
        "ip": dev.ip,
        "status": dev.status,
        "tags": dev.tags,
        "timestamp": dev.last_seen.isoformat(),
    }


@router.get("/stream")
async def sse_stream():
    """Server-Sent Events stream of all device tags, pushed every poll interval."""

    async def event_generator():
        seq = 0
        while True:
            snapshot = discovery_daemon.get_all_tags()
            data = json.dumps(snapshot, default=str)
            seq += 1
            # Build SSE frame: split data across multiple data: lines
            # to stay under browser buffer limits (SSE spec: consecutive
            # data: lines are concatenated with \n by the client)
            lines = [f"id: {seq}_{time.time():.3f}", "event: tags"]
            for i in range(0, len(data), _SSE_CHUNK_SIZE):
                lines.append(f"data: {data[i:i + _SSE_CHUNK_SIZE]}")
            lines.append("")  # trailing blank line ends the event
            lines.append("")
            yield "\n".join(lines)
            await asyncio.sleep(settings.discovery_poll_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
