#!/usr/bin/env python3
"""
Media Offload Agent
===================
Syncs media from multiple devices to Google Drive (2TB).

Monitors:
- Local watch folders (travel laptop)
- Remote folders via Jarvis Node (PLC laptop)
- Telegram inbox (from TelegramMediaHandler)

Syncs to:
- gdrive:factorylm-archives/media/<source>/<date>/

Runs as background service with configurable poll interval.
"""

import os
import sys
import json
import asyncio
import logging
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import httpx

logger = logging.getLogger(__name__)


class MediaOffloadAgent:
    """
    Centralized media collection from all field devices.

    Runs on: VPS (100.68.120.99) or Travel Laptop
    Schedule: Every 60 seconds
    Storage: gdrive:factorylm-archives/media/
    """

    def __init__(
        self,
        gdrive_remote: str = "gdrive:factorylm-archives/media",
        staging_dir: Optional[str] = None,
        poll_interval: int = 60,
        jarvis_plc_url: str = "http://100.72.2.99:8765"
    ):
        """Initialize media offload agent."""
        self.gdrive_remote = gdrive_remote
        self.staging_dir = Path(staging_dir) if staging_dir else Path.home() / ".openclaw" / "media-staging"
        self.poll_interval = poll_interval
        self.jarvis_plc_url = jarvis_plc_url

        # Create staging directory
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        # Track last check times per source
        self.last_check = {}

        # Device configurations
        self.devices = {
            "travel-laptop": {
                "type": "local",
                "watch_folders": [
                    Path.home() / "Desktop" / "Captures",
                    Path.home() / "Downloads" / "Screenshots",
                    Path.home() / "Pictures" / "Screenshots",
                    Path.home() / "Videos" / "Captures",
                ],
                "extensions": [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".avi", ".webm", ".pdf"]
            },
            "telegram": {
                "type": "local",
                "watch_folders": [
                    Path.home() / ".openclaw" / "media-inbox" / "telegram"
                ],
                "extensions": [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".pdf", ".webp"]
            },
            "plc-laptop": {
                "type": "remote",
                "jarvis_url": jarvis_plc_url,
                "watch_folders": [
                    "C:/Users/hharp/Pictures/Screenshots",
                    "C:/Users/hharp/Videos/FactoryIO",
                    "C:/Users/hharp/Desktop/PLCExports",
                ],
                "extensions": [".jpg", ".jpeg", ".png", ".mp4", ".mov", ".csv", ".pdf"]
            }
        }

        # HTTP client for Jarvis Node
        self.http = httpx.AsyncClient(timeout=30)

        logger.info(f"Media Offload Agent initialized")
        logger.info(f"  Staging: {self.staging_dir}")
        logger.info(f"  GDrive: {self.gdrive_remote}")
        logger.info(f"  Poll interval: {self.poll_interval}s")

    async def check_device_online(self, device_name: str) -> bool:
        """Check if a device is online and accessible."""
        device = self.devices.get(device_name)
        if not device:
            return False

        if device["type"] == "local":
            # Check if any watch folder exists
            for folder in device["watch_folders"]:
                if folder.exists():
                    return True
            return False

        elif device["type"] == "remote":
            # Ping Jarvis Node
            try:
                resp = await self.http.get(f"{device['jarvis_url']}/health", timeout=5)
                return resp.status_code == 200
            except:
                return False

        return False

    async def discover_devices(self) -> Dict[str, bool]:
        """Check which devices are online."""
        status = {}
        for device_name in self.devices:
            status[device_name] = await self.check_device_online(device_name)
            logger.debug(f"Device {device_name}: {'online' if status[device_name] else 'offline'}")
        return status

    def get_local_new_files(self, folder: Path, extensions: List[str], since: float) -> List[Path]:
        """Get new files from local folder since timestamp."""
        if not folder.exists():
            return []

        new_files = []
        for ext in extensions:
            for f in folder.rglob(f"*{ext}"):
                try:
                    if f.stat().st_mtime > since:
                        new_files.append(f)
                except:
                    pass

        return new_files

    async def get_remote_new_files(self, device: Dict, folder: str, since: float) -> List[Dict]:
        """Get new files from remote folder via Jarvis Node."""
        try:
            resp = await self.http.post(
                f"{device['jarvis_url']}/files/list",
                json={
                    "path": folder,
                    "recursive": True,
                    "extensions": device["extensions"]
                },
                timeout=30
            )

            if resp.status_code != 200:
                return []

            files = resp.json().get("files", [])
            # Filter by modification time
            new_files = [f for f in files if f.get("mtime", 0) > since]
            return new_files

        except Exception as e:
            logger.debug(f"Failed to list remote files: {e}")
            return []

    async def download_remote_file(self, device: Dict, remote_path: str) -> Optional[Path]:
        """Download file from remote device via Jarvis Node."""
        try:
            resp = await self.http.post(
                f"{device['jarvis_url']}/files/read",
                json={"path": remote_path, "binary": True},
                timeout=60
            )

            if resp.status_code != 200:
                return None

            data = resp.json()
            content = data.get("content")
            if not content:
                return None

            # Decode base64 content
            import base64
            file_bytes = base64.b64decode(content)

            # Save to staging
            filename = Path(remote_path).name
            staging_path = self.staging_dir / "plc-laptop" / datetime.now().strftime("%Y-%m-%d") / filename
            staging_path.parent.mkdir(parents=True, exist_ok=True)
            staging_path.write_bytes(file_bytes)

            return staging_path

        except Exception as e:
            logger.error(f"Failed to download {remote_path}: {e}")
            return None

    def stage_local_file(self, file_path: Path, device_name: str) -> Path:
        """Copy local file to staging area."""
        date_folder = datetime.now().strftime("%Y-%m-%d")
        staging_path = self.staging_dir / device_name / date_folder / file_path.name
        staging_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file (don't move - leave original)
        shutil.copy2(file_path, staging_path)
        return staging_path

    async def sync_to_gdrive(self, device_name: str) -> Dict[str, Any]:
        """Sync staged files to Google Drive using rclone."""
        staging_device_dir = self.staging_dir / device_name
        if not staging_device_dir.exists():
            return {"synced": 0, "error": None}

        gdrive_path = f"{self.gdrive_remote}/{device_name}/"

        try:
            # Run rclone sync
            result = subprocess.run(
                [
                    "rclone", "copy",
                    str(staging_device_dir),
                    gdrive_path,
                    "--progress",
                    "--log-level", "INFO"
                ],
                capture_output=True,
                text=True,
                timeout=300  # 5 min timeout
            )

            if result.returncode == 0:
                # Count synced files
                file_count = sum(1 for _ in staging_device_dir.rglob("*") if _.is_file())
                logger.info(f"Synced {file_count} files from {device_name} to {gdrive_path}")

                # Clean staging after successful sync
                # shutil.rmtree(staging_device_dir)  # Uncomment to auto-clean

                return {"synced": file_count, "error": None}
            else:
                return {"synced": 0, "error": result.stderr}

        except subprocess.TimeoutExpired:
            return {"synced": 0, "error": "Sync timeout"}
        except FileNotFoundError:
            return {"synced": 0, "error": "rclone not installed"}
        except Exception as e:
            return {"synced": 0, "error": str(e)}

    async def process_device(self, device_name: str) -> Dict[str, Any]:
        """Process a single device - detect new files and stage them."""
        device = self.devices.get(device_name)
        if not device:
            return {"error": "Unknown device"}

        since = self.last_check.get(device_name, 0)
        new_files = []
        staged_files = []

        if device["type"] == "local":
            for folder in device["watch_folders"]:
                files = self.get_local_new_files(folder, device["extensions"], since)
                for f in files:
                    try:
                        staged = self.stage_local_file(f, device_name)
                        staged_files.append(str(staged))
                        new_files.append(str(f))
                    except Exception as e:
                        logger.error(f"Failed to stage {f}: {e}")

        elif device["type"] == "remote":
            for folder in device["watch_folders"]:
                files = await self.get_remote_new_files(device, folder, since)
                for f in files:
                    try:
                        staged = await self.download_remote_file(device, f["path"])
                        if staged:
                            staged_files.append(str(staged))
                            new_files.append(f["path"])
                    except Exception as e:
                        logger.error(f"Failed to download {f}: {e}")

        # Update last check time
        self.last_check[device_name] = datetime.now().timestamp()

        return {
            "device": device_name,
            "new_files": len(new_files),
            "staged_files": staged_files
        }

    async def run_once(self) -> Dict[str, Any]:
        """Run one iteration of the offload process."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "devices": {},
            "synced": {}
        }

        # Check which devices are online
        device_status = await self.discover_devices()

        # Process each online device
        for device_name, online in device_status.items():
            if online:
                result = await self.process_device(device_name)
                results["devices"][device_name] = result

                # Sync to Google Drive if we have new files
                if result.get("staged_files"):
                    sync_result = await self.sync_to_gdrive(device_name)
                    results["synced"][device_name] = sync_result
            else:
                results["devices"][device_name] = {"status": "offline"}

        return results

    async def run(self):
        """Run continuous offload loop."""
        logger.info("Starting Media Offload Agent loop...")

        while True:
            try:
                results = await self.run_once()

                # Log summary
                total_new = sum(d.get("new_files", 0) for d in results["devices"].values() if isinstance(d, dict))
                total_synced = sum(s.get("synced", 0) for s in results["synced"].values())

                if total_new > 0 or total_synced > 0:
                    logger.info(f"Poll complete: {total_new} new files, {total_synced} synced")

            except Exception as e:
                logger.error(f"Poll error: {e}")

            await asyncio.sleep(self.poll_interval)

    async def cleanup_staging(self, days_old: int = 7):
        """Remove old files from staging area."""
        cutoff = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        removed = 0

        for device_dir in self.staging_dir.iterdir():
            if device_dir.is_dir():
                for date_dir in device_dir.iterdir():
                    if date_dir.is_dir():
                        try:
                            # Parse date from folder name
                            folder_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                            if folder_date.timestamp() < cutoff:
                                shutil.rmtree(date_dir)
                                removed += 1
                        except:
                            pass

        return removed


# CLI interface
async def main():
    """Run media offload agent."""
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.INFO
    )

    agent = MediaOffloadAgent()

    # Single run for testing
    if "--once" in sys.argv:
        results = await agent.run_once()
        print(json.dumps(results, indent=2))
    else:
        # Continuous loop
        await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
