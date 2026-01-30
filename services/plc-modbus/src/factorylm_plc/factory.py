"""
Factory function for creating PLC clients.

Provides a simple interface for creating the appropriate PLC client
based on configuration.
"""

import os
from typing import Optional

from .base import BasePLCClient
from .mock_plc import MockPLC
from .micro820 import Micro820PLC
from .factory_io import FactoryIOMicro820


def create_plc_client(
    plc_type: str = None,
    host: str = None,
    port: int = None,
    timeout: float = None,
    retries: int = None,
    scene_name: str = None,
) -> BasePLCClient:
    """
    Factory function to create PLC clients.

    Creates the appropriate PLC client based on the specified type.
    If parameters are not provided, attempts to load from environment variables.

    Args:
        plc_type: Type of PLC client to create:
            - "mock" - Mock PLC for testing (no network)
            - "micro820" - Generic Allen-Bradley Micro 820
            - "factoryio_micro820" - Factory I/O + Micro 820 combo
        host: PLC IP address or hostname.
        port: Modbus TCP port (default 502).
        timeout: Connection timeout in seconds (default 5).
        retries: Number of retry attempts (default 3).
        scene_name: Factory I/O scene name (for factoryio_micro820).

    Returns:
        BasePLCClient: Configured PLC client instance.

    Raises:
        ValueError: If unknown plc_type specified.

    Environment Variables:
        PLC_TYPE: Default PLC type if not specified.
        PLC_HOST: Default host if not specified.
        PLC_PORT: Default port if not specified.
        PLC_TIMEOUT: Default timeout if not specified.
        PLC_RETRY_COUNT: Default retry count if not specified.
        FACTORY_IO_SCENE: Default scene name if not specified.
        USE_MOCK_PLC: If "true", override to use mock PLC.
    """
    # Load defaults from environment
    plc_type = plc_type or os.getenv("PLC_TYPE", "mock")
    host = host or os.getenv("PLC_HOST", "localhost")
    port = port or int(os.getenv("PLC_PORT", "502"))
    timeout = timeout or float(os.getenv("PLC_TIMEOUT", "5"))
    retries = retries or int(os.getenv("PLC_RETRY_COUNT", "3"))
    scene_name = scene_name or os.getenv("FACTORY_IO_SCENE", "sorting_station")

    # Check for mock override
    use_mock = os.getenv("USE_MOCK_PLC", "false").lower() == "true"
    if use_mock:
        plc_type = "mock"

    # Normalize type string
    plc_type = plc_type.lower().strip()

    # Create appropriate client
    if plc_type == "mock":
        return MockPLC()

    elif plc_type == "micro820":
        return Micro820PLC(
            host=host,
            port=port,
            timeout=timeout,
            retries=retries,
        )

    elif plc_type in ("factoryio_micro820", "factoryio", "factory_io"):
        return FactoryIOMicro820(
            host=host,
            port=port,
            timeout=timeout,
            retries=retries,
            scene_name=scene_name,
        )

    else:
        raise ValueError(
            f"Unknown PLC type: {plc_type}. "
            f"Valid types: mock, micro820, factoryio_micro820"
        )


def create_managed_client(
    plc_type: str = None,
    host: str = None,
    port: int = None,
    timeout: float = None,
    retries: int = None,
    scene_name: str = None,
    auto_reconnect: bool = True,
):
    """
    Create a PLC client wrapped in a connection manager.

    Provides automatic reconnection and retry logic for production use.

    Args:
        plc_type: Type of PLC client (see create_plc_client).
        host: PLC IP address or hostname.
        port: Modbus TCP port.
        timeout: Connection timeout in seconds.
        retries: Number of retry attempts.
        scene_name: Factory I/O scene name.
        auto_reconnect: Whether to auto-reconnect on failure.

    Returns:
        PLCConnectionManager: Connection manager wrapping the client.
    """
    from .connection_manager import PLCConnectionManager

    client = create_plc_client(
        plc_type=plc_type,
        host=host,
        port=port,
        timeout=timeout,
        retries=retries,
        scene_name=scene_name,
    )

    return PLCConnectionManager(
        client=client,
        retry_count=retries or 3,
        retry_delay=1.0,
        auto_reconnect=auto_reconnect,
    )
