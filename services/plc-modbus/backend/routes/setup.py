"""Setup routes for initial configuration and network scanning."""

import logging

from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.models import ScanRequest, ScanResponse
from backend.services import NetworkScanner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])


@router.post("/scan-network", response_model=ScanResponse)
async def scan_network(request: ScanRequest = None) -> ScanResponse:
    """
    Scan the network for Modbus TCP devices.

    Performs a parallel scan of the specified subnet range to discover
    devices listening on port 502 (Modbus TCP).

    Args:
        request: Optional scan parameters. Uses defaults if not provided.

    Returns:
        ScanResponse with list of discovered devices and scan statistics.
    """
    # Use defaults if no request body provided
    if request is None:
        request = ScanRequest()

    # Validate start <= end
    if request.start > request.end:
        raise HTTPException(
            status_code=400,
            detail=f"start ({request.start}) must be <= end ({request.end})",
        )

    logger.info(
        f"Starting network scan: {request.subnet}.{request.start}-{request.end} "
        f"(timeout={request.timeout}s)"
    )

    scanner = NetworkScanner(
        timeout=request.timeout,
        port=settings.scanner_default_port,
        max_workers=settings.scanner_max_workers,
    )

    try:
        devices, count, duration = scanner.get_online_devices(
            subnet=request.subnet,
            start=request.start,
            end=request.end,
        )
    except Exception as e:
        logger.error(f"Network scan failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Network scan failed: {str(e)}",
        )

    return ScanResponse(
        devices=devices,
        count=count,
        online_count=len(devices),
        scan_time_seconds=round(duration, 2),
        subnet_scanned=f"{request.subnet}.{request.start}-{request.end}",
    )
