# Restored from: feature/rideview-continuous-improvement:projects/factorylm/puppeteer/bot.py
"""
Atlas CMMS client for work order creation.
"""

import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class CMSSClient:
    """Atlas CMMS API client for work order management."""

    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.token: Optional[str] = None

    async def login(self) -> bool:
        """Authenticate and obtain a bearer token."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/auth/signin",
                    json={"email": self.email, "password": self.password, "type": "client"},
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.token = data.get("accessToken")
                        logger.info("CMMS login successful")
                        return True
                    logger.error(f"CMMS login failed: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"CMMS login error: {e}")
            return False

    async def test_connection(self) -> bool:
        """Pre-flight check — verify the CMMS endpoint is reachable."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    reachable = resp.status < 500
                    logger.info(f"CMMS health check: status={resp.status} reachable={reachable}")
                    return reachable
        except Exception as e:
            logger.warning(f"CMMS unreachable: {e}")
            return False

    async def create_work_order(
        self, title: str, description: str, priority: str = "MEDIUM"
    ) -> Optional[dict]:
        """Create a work order in Atlas CMMS."""
        if not self.token:
            if not await self.login():
                return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/work-orders",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={
                        "title": title,
                        "description": description,
                        "priority": priority,
                    },
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        logger.info(f"Work order created: {data.get('id')}")
                        return data
                    text = await resp.text()
                    logger.error(f"WO creation failed: {resp.status} - {text}")
                    return None
        except Exception as e:
            logger.error(f"WO creation error: {e}")
            return None
