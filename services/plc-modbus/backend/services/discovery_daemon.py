"""Auto-discovery daemon for EtherNet/IP (CIP) devices on the local subnet."""

import asyncio
import logging
import socket
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

try:
    from pycomm3 import LogixDriver
    HAS_PYCOMM3 = True
except ImportError:
    LogixDriver = None  # type: ignore[assignment,misc]
    HAS_PYCOMM3 = False

from backend.config import settings

logger = logging.getLogger(__name__)

if not HAS_PYCOMM3:
    logger.warning("pycomm3 not installed — EtherNet/IP discovery disabled")

ETHERNET_IP_PORT = 44818


@dataclass
class DeviceState:
    ip: str
    port: int = ETHERNET_IP_PORT
    status: str = "online"  # online | polling | offline
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    tags: dict = field(default_factory=dict)
    tag_list: list = field(default_factory=list)
    plc_info: dict = field(default_factory=dict)
    _driver: Optional[Any] = field(default=None, repr=False)
    _miss_count: int = field(default=0, repr=False)


def _detect_subnet() -> str:
    """Detect /24 subnet from the first non-loopback interface."""
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show"], text=True, timeout=5
        )
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet ") and "127.0.0.1" not in line:
                addr = line.split()[1].split("/")[0]
                parts = addr.split(".")
                if len(parts) == 4:
                    subnet = ".".join(parts[:3])
                    logger.info(f"Detected subnet: {subnet}")
                    return subnet
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    # macOS fallback
    try:
        out = subprocess.check_output(["ifconfig"], text=True, timeout=5)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet ") and "127.0.0.1" not in line:
                addr = line.split()[1]
                parts = addr.split(".")
                if len(parts) == 4:
                    subnet = ".".join(parts[:3])
                    logger.info(f"Detected subnet (macOS): {subnet}")
                    return subnet
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    logger.warning("Could not detect subnet, falling back to 192.168.1")
    return "192.168.1"


def _probe_port(ip: str, port: int, timeout: float = 0.5) -> bool:
    """Quick TCP connect probe — returns True if port is open."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def _scan_subnet_for_eip(subnet: str, start: int = 1, end: int = 254,
                         timeout: float = 0.3, max_workers: int = 50) -> list[str]:
    """Scan subnet for hosts with port 44818 open (EtherNet/IP)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ips = [f"{subnet}.{i}" for i in range(start, end + 1)]
    found: list[str] = []

    logger.info(f"Scanning {len(ips)} IPs on {subnet}.{start}-{end}:{ETHERNET_IP_PORT}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_probe_port, ip, ETHERNET_IP_PORT, timeout): ip
            for ip in ips
        }
        for future in as_completed(futures):
            ip = futures[future]
            if future.result():
                logger.info(f"Found EtherNet/IP device at {ip}:{ETHERNET_IP_PORT}")
                found.append(ip)

    logger.info(f"Scan complete: {len(found)} EtherNet/IP device(s) found")
    return found


def _connect_and_discover(ip: str) -> tuple[LogixDriver, list[dict], dict]:
    """Open a LogixDriver, get tag list and PLC info."""
    driver = LogixDriver(ip)
    driver.open()
    tag_list = driver.get_tag_list()
    info = driver.info or {}
    return driver, tag_list, info


def _read_all_tags(driver: LogixDriver, tag_names: list[str]) -> dict[str, Any]:
    """Read all tags in one batch call. Returns {name: value}."""
    if not tag_names:
        return {}
    results = driver.read(*tag_names)
    # Single tag read returns a single Tag, not a list
    if not isinstance(results, list):
        results = [results]
    out = {}
    for r in results:
        if r.error:
            out[r.tag] = f"ERROR: {r.error}"
        else:
            out[r.tag] = r.value
    return out


def _close_driver(driver: LogixDriver):
    """Safely close a LogixDriver."""
    try:
        driver.close()
    except Exception:
        pass


class DiscoveryDaemon:
    """Background service that discovers and polls EtherNet/IP PLCs."""

    def __init__(self):
        self.devices: dict[str, DeviceState] = {}
        self._subnet: str = settings.scanner_default_subnet
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._poll_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the discovery scan and poll loops."""
        if not HAS_PYCOMM3:
            logger.warning("Skipping EtherNet/IP discovery — pycomm3 not installed")
            return
        self._subnet = await asyncio.to_thread(_detect_subnet)
        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(f"Discovery daemon started on subnet {self._subnet}")

    async def stop(self):
        """Gracefully stop all loops and disconnect drivers."""
        self._running = False
        for task in (self._scan_task, self._poll_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        for dev in self.devices.values():
            if dev._driver:
                await asyncio.to_thread(_close_driver, dev._driver)
        logger.info("Discovery daemon stopped")

    async def _scan_loop(self):
        """Periodically scan for EtherNet/IP devices on port 44818."""
        while self._running:
            try:
                found_ips = await asyncio.to_thread(
                    _scan_subnet_for_eip,
                    self._subnet,
                    settings.scanner_default_start,
                    settings.scanner_default_end,
                    settings.scanner_default_timeout,
                    settings.scanner_max_workers,
                )
                found_set = set(found_ips)

                # Connect to new devices
                for ip in found_ips:
                    if ip not in self.devices:
                        try:
                            driver, tag_list, info = await asyncio.to_thread(
                                _connect_and_discover, ip
                            )
                            tag_names = [t["tag_name"] for t in tag_list]
                            product = info.get("product_name", "Unknown PLC")
                            self.devices[ip] = DeviceState(
                                ip=ip,
                                status="polling",
                                tag_list=tag_names,
                                plc_info=info,
                                _driver=driver,
                            )
                            logger.info(
                                f"Connected to {ip}: {product}, {len(tag_names)} tags"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to connect to {ip}: {e}")
                            self.devices[ip] = DeviceState(ip=ip, status="online")
                    else:
                        dev = self.devices[ip]
                        dev.last_seen = datetime.now()
                        dev._miss_count = 0
                        # Reconnect if it was offline
                        if dev.status == "offline":
                            try:
                                driver, tag_list, info = await asyncio.to_thread(
                                    _connect_and_discover, ip
                                )
                                tag_names = [t["tag_name"] for t in tag_list]
                                dev._driver = driver
                                dev.tag_list = tag_names
                                dev.plc_info = info
                                dev.status = "polling"
                                logger.info(f"Reconnected to {ip}")
                            except Exception as e:
                                logger.warning(f"Reconnect failed for {ip}: {e}")

                # Mark missing devices
                for ip, dev in self.devices.items():
                    if ip not in found_set and dev.status != "offline":
                        dev._miss_count += 1
                        if dev._miss_count >= 3:
                            dev.status = "offline"
                            if dev._driver:
                                await asyncio.to_thread(_close_driver, dev._driver)
                                dev._driver = None
                            logger.info(f"Device offline: {ip}")

            except Exception as e:
                logger.error(f"Scan loop error: {e}")

            await asyncio.sleep(settings.discovery_scan_interval)

    async def _poll_loop(self):
        """Read tags from all polling devices at the configured interval."""
        while self._running:
            for dev in list(self.devices.values()):
                if dev.status != "polling" or dev._driver is None:
                    continue
                try:
                    values = await asyncio.wait_for(
                        asyncio.to_thread(
                            _read_all_tags, dev._driver, dev.tag_list
                        ),
                        timeout=5.0,
                    )
                    dev.tags = values
                    dev.last_seen = datetime.now()
                    logger.debug(f"Polled {dev.ip}: {len(values)} tags")
                except asyncio.TimeoutError:
                    logger.warning(f"Poll timeout for {dev.ip} (>5s), reconnecting")
                    dev.status = "online"
                    if dev._driver:
                        await asyncio.to_thread(_close_driver, dev._driver)
                        dev._driver = None
                except Exception as e:
                    logger.warning(f"Poll error for {dev.ip}: {e}")
                    dev.status = "online"
                    if dev._driver:
                        await asyncio.to_thread(_close_driver, dev._driver)
                        dev._driver = None

            await asyncio.sleep(settings.discovery_poll_interval)

    def get_all_tags(self) -> dict:
        """Return a snapshot of all devices and their latest tag values."""
        result = {}
        for ip, dev in self.devices.items():
            result[ip] = {
                "status": dev.status,
                "product": dev.plc_info.get("product_name", ""),
                "tags": dev.tags,
                "tag_count": len(dev.tag_list),
                "timestamp": dev.last_seen.isoformat(),
            }
        return result


# Global singleton — started/stopped by FastAPI lifespan
discovery_daemon = DiscoveryDaemon()
