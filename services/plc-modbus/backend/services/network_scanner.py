"""Network scanner service for discovering Modbus TCP devices."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from pymodbus.client import ModbusTcpClient

from backend.models.scan_models import DeviceInfo, ScanResult

logger = logging.getLogger(__name__)


class NetworkScanner:
    """
    Parallel network scanner for Modbus TCP devices.

    Scans a subnet range for devices listening on the Modbus TCP port (502).
    Uses ThreadPoolExecutor for parallel probing.
    """

    def __init__(
        self,
        timeout: float = 0.3,
        port: int = 502,
        max_workers: int = 50,
    ):
        """
        Initialize the network scanner.

        Args:
            timeout: Connection timeout in seconds (default 0.3).
            port: Modbus TCP port to scan (default 502).
            max_workers: Maximum concurrent connections (default 50).
        """
        self.timeout = timeout
        self.port = port
        self.max_workers = max_workers

    def _probe_ip(self, ip: str) -> ScanResult:
        """
        Probe a single IP address for Modbus TCP connectivity.

        Args:
            ip: IP address to probe.

        Returns:
            ScanResult with status and response time.
        """
        start_time = time.perf_counter()

        try:
            client = ModbusTcpClient(
                host=ip,
                port=self.port,
                timeout=self.timeout,
                retries=0,
            )

            connected = client.connect()
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if connected:
                client.close()
                return ScanResult(
                    ip=ip,
                    port=self.port,
                    status="online",
                    response_time_ms=round(elapsed_ms, 2),
                )
            else:
                return ScanResult(
                    ip=ip,
                    port=self.port,
                    status="connection_refused",
                )

        except TimeoutError:
            return ScanResult(
                ip=ip,
                port=self.port,
                status="timeout",
            )
        except ConnectionRefusedError:
            return ScanResult(
                ip=ip,
                port=self.port,
                status="connection_refused",
            )
        except OSError as e:
            # Network unreachable, host unreachable, etc.
            if "timed out" in str(e).lower():
                return ScanResult(
                    ip=ip,
                    port=self.port,
                    status="timeout",
                )
            return ScanResult(
                ip=ip,
                port=self.port,
                status="error",
                error_message=str(e),
            )
        except Exception as e:
            logger.debug(f"Error probing {ip}: {e}")
            return ScanResult(
                ip=ip,
                port=self.port,
                status="error",
                error_message=str(e),
            )

    def scan_subnet(
        self,
        subnet: str = "192.168.1",
        start: int = 1,
        end: int = 254,
    ) -> tuple[list[ScanResult], float]:
        """
        Scan a subnet range for Modbus TCP devices.

        Args:
            subnet: Subnet prefix (e.g., "192.168.1").
            start: Starting IP suffix (1-254).
            end: Ending IP suffix (1-254).

        Returns:
            Tuple of (list of all scan results, scan duration in seconds).
        """
        ips = [f"{subnet}.{i}" for i in range(start, end + 1)]
        results: list[ScanResult] = []

        logger.info(f"Scanning {len(ips)} IPs on {subnet}.{start}-{end}:{self.port}")
        scan_start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ip = {executor.submit(self._probe_ip, ip): ip for ip in ips}

            for future in as_completed(future_to_ip):
                result = future.result()
                results.append(result)
                if result.status == "online":
                    logger.info(
                        f"Found Modbus device at {result.ip}:{result.port} "
                        f"({result.response_time_ms}ms)"
                    )

        scan_duration = time.perf_counter() - scan_start
        logger.info(
            f"Scan complete: {len(results)} IPs in {scan_duration:.2f}s, "
            f"{sum(1 for r in results if r.status == 'online')} online"
        )

        return results, scan_duration

    def get_online_devices(
        self,
        subnet: str = "192.168.1",
        start: int = 1,
        end: int = 254,
    ) -> tuple[list[DeviceInfo], int, float]:
        """
        Scan subnet and return only online devices.

        Args:
            subnet: Subnet prefix (e.g., "192.168.1").
            start: Starting IP suffix (1-254).
            end: Ending IP suffix (1-254).

        Returns:
            Tuple of (list of online devices, total IPs scanned, scan duration).
        """
        results, duration = self.scan_subnet(subnet, start, end)

        online_devices = [
            DeviceInfo(
                ip=r.ip,
                port=r.port,
                status="online",
                response_time_ms=r.response_time_ms or 0.0,
            )
            for r in results
            if r.status == "online"
        ]

        # Sort by response time (fastest first)
        online_devices.sort(key=lambda d: d.response_time_ms)

        return online_devices, len(results), duration
