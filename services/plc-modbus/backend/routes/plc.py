"""PLC routes for status, I/O, connection, and control."""

import logging

from fastapi import APIRouter, HTTPException

from backend.models.plc_models import (
    PLCStatusResponse,
    ConnectRequest,
    ConnectResponse,
    IOResponse,
    WriteCoilRequest,
    WriteCoilResponse,
)
from backend.services.plc_connection import plc_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plc", tags=["plc"])


@router.get("/status", response_model=PLCStatusResponse)
async def get_plc_status() -> PLCStatusResponse:
    """
    Get PLC connection status.

    Returns current connection state, IP address, port, and last successful
    communication timestamp.
    """
    status = plc_service.get_status()
    return PLCStatusResponse(**status)


@router.get("/io", response_model=IOResponse)
async def get_plc_io() -> IOResponse:
    """
    Read all I/O from the PLC.

    Returns all coils (program variables, inputs, outputs) and holding registers.
    Requires active PLC connection.
    """
    if not plc_service.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Not connected to PLC. Use POST /api/plc/connect first.",
        )

    try:
        io_data = plc_service.read_io()
        return IOResponse(
            coils=io_data["coils"],
            inputs=io_data["inputs"],
            outputs=io_data["outputs"],
            registers=io_data["registers"],
            timestamp=io_data["timestamp"],
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"I/O read failed: {str(e)}")


@router.post("/connect", response_model=ConnectResponse)
async def connect_to_plc(request: ConnectRequest) -> ConnectResponse:
    """
    Connect to a PLC via Modbus TCP.

    Establishes a connection to the specified PLC. Any existing connection
    will be disconnected first.
    """
    logger.info(f"Connecting to PLC at {request.ip}:{request.port}")
    result = plc_service.connect(ip=request.ip, port=request.port)
    return ConnectResponse(**result)


@router.post("/write-coil", response_model=WriteCoilResponse)
async def write_coil(request: WriteCoilRequest) -> WriteCoilResponse:
    """
    Write a value to a PLC coil.

    Only coils in the writable range (0-6 program vars, 15-17 outputs) can be written.
    Requires active PLC connection.
    """
    if not plc_service.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Not connected to PLC. Use POST /api/plc/connect first.",
        )

    try:
        result = plc_service.write_coil(address=request.address, value=request.value)
        return WriteCoilResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Write failed: {str(e)}")
