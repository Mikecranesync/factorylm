"""Tests for the async relay daemon."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

from factorylm.models import AgentConfig, DiscordConfig, FactoryLMConfig, RelayConfig
from factorylm.relay.daemon import AsyncRelayDaemon


@pytest.fixture
def config():
    return FactoryLMConfig(
        discord=DiscordConfig(
            guild_id=999,
            agents={
                "tony": AgentConfig(
                    name="Tony",
                    webhook_url="https://discord.com/api/webhooks/1/abc",
                    channel_id=100,
                    machine="Mac Mini",
                    role="Boss agent",
                ),
                "ultron": AgentConfig(
                    name="Ultron",
                    webhook_url="https://discord.com/api/webhooks/2/def",
                    channel_id=200,
                    machine="VPS",
                    role="Cloud reasoning",
                ),
            },
        ),
        relay=RelayConfig(host="127.0.0.1", port=8765),
    )


@pytest.fixture
def daemon(config):
    return AsyncRelayDaemon(config)


@pytest.fixture
async def client(daemon):
    server = TestServer(daemon.app)
    async with TestClient(server) as c:
        yield c
    await daemon.close()


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert data["status"] == "healthy"
        assert data["service"] == "factorylm-discord-relay"
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert data["guilds_count"] == 1
        assert data["guild_id"] == 999  # From config fixture
        assert "last_heartbeat" in data  # Can be None initially
        assert data["version"] == "1.0.0"


class TestStatus:
    @pytest.mark.asyncio
    async def test_status_returns_agents(self, client):
        resp = await client.get("/status")
        assert resp.status == 200
        data = await resp.json()
        assert "tony" in data["agents"]
        assert "ultron" in data["agents"]
        assert data["agents"]["tony"]["machine"] == "Mac Mini"
        assert "queue_depth" in data
        assert "uptime_seconds" in data
        assert "messages_relayed" in data


class TestRelay:
    @pytest.mark.asyncio
    async def test_relay_valid_agent(self, client, daemon):
        with patch.object(daemon, "_send_webhook", new_callable=AsyncMock, return_value=True):
            resp = await client.post(
                "/relay",
                json={"agent": "tony", "message": "Hello from test"},
            )
        assert resp.status == 202
        data = await resp.json()
        assert data["status"] == "queued"
        assert data["agent"] == "tony"

    @pytest.mark.asyncio
    async def test_relay_unknown_agent(self, client):
        resp = await client.post(
            "/relay",
            json={"agent": "unknown_bot", "message": "Hello"},
        )
        assert resp.status == 404
        data = await resp.json()
        assert "unknown_bot" in data["error"]
        assert "known_agents" in data

    @pytest.mark.asyncio
    async def test_relay_missing_fields(self, client):
        resp = await client.post("/relay", json={"agent": "tony"})
        assert resp.status == 400
        data = await resp.json()
        assert "required" in data["error"]

    @pytest.mark.asyncio
    async def test_relay_invalid_json(self, client):
        resp = await client.post(
            "/relay",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_relay_increments_count(self, client, daemon):
        assert daemon._message_count == 0
        with patch.object(daemon, "_send_webhook", new_callable=AsyncMock, return_value=True):
            await client.post("/relay", json={"agent": "tony", "message": "msg1"})
            await client.post("/relay", json={"agent": "ultron", "message": "msg2"})
        assert daemon._message_count == 2

    @pytest.mark.asyncio
    async def test_heartbeat_field_exists(self, client):
        """Test that the heartbeat field exists in health response (can be None initially)."""
        health_resp = await client.get("/health")
        health_data = await health_resp.json()
        assert "last_heartbeat" in health_data
        # Initially it can be None (no messages sent yet)
        
    @pytest.mark.asyncio
    async def test_heartbeat_initial_state(self, daemon):
        """Test that heartbeat is initialized as None and can be updated."""
        # Initially heartbeat should be None
        assert daemon._last_heartbeat is None
        
        # We can set it manually to simulate a successful send
        import time
        test_time = time.time()
        daemon._last_heartbeat = test_time
        assert daemon._last_heartbeat == test_time


class TestGracefulShutdown:
    @pytest.mark.asyncio
    async def test_close_cancels_drain(self, daemon):
        import asyncio

        daemon._drain_task = asyncio.create_task(daemon._drain_worker())
        await daemon.close()
        # Let the cancellation propagate
        await asyncio.sleep(0)
        assert daemon._drain_task.cancelled() or daemon._drain_task.done()
