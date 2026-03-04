"""Smoke tests for conveyor-relay service."""

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from relay import (
    CommandRequest,
    VALID_ACTIONS,
    _check_rate_limit,
    _last_command,
    app,
)


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    """Reset rate limiter between tests."""
    _last_command.clear()
    yield
    _last_command.clear()


client = TestClient(app)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestCommandValidation:
    def test_valid_actions_set(self):
        assert VALID_ACTIONS == {"forward", "reverse", "stop", "set_speed"}

    def test_command_request_requires_action(self):
        with pytest.raises(Exception):
            CommandRequest()

    def test_command_request_accepts_valid_action(self):
        cmd = CommandRequest(action="forward")
        assert cmd.action == "forward"
        assert cmd.value is None

    def test_command_request_with_speed(self):
        cmd = CommandRequest(action="set_speed", value=45.0)
        assert cmd.value == 45.0

    def test_invalid_action_rejected(self):
        resp = client.post("/api/command", json={"action": "explode"})
        assert resp.status_code == 400
        assert "Invalid action" in resp.json()["detail"]

    def test_set_speed_requires_value(self):
        resp = client.post("/api/command", json={"action": "set_speed"})
        assert resp.status_code == 400
        assert "value required" in resp.json()["detail"]

    def test_set_speed_rejects_out_of_range(self):
        resp = client.post("/api/command", json={"action": "set_speed", "value": 100})
        assert resp.status_code == 400
        assert "between 0 and 60" in resp.json()["detail"]

    def test_set_speed_rejects_negative(self):
        resp = client.post("/api/command", json={"action": "set_speed", "value": -5})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_first_request_allowed(self):
        assert _check_rate_limit("192.168.1.1") is True

    def test_second_request_blocked(self):
        _check_rate_limit("192.168.1.2")
        assert _check_rate_limit("192.168.1.2") is False

    def test_different_ips_independent(self):
        _check_rate_limit("10.0.0.1")
        assert _check_rate_limit("10.0.0.2") is True

    def test_request_allowed_after_cooldown(self):
        _last_command["10.0.0.3"] = time.time() - 10  # 10s ago
        assert _check_rate_limit("10.0.0.3") is True


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "conveyor-relay"
        assert "commandCount" in data
        assert "backendUrl" in data

    def test_control_page_serves_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Status endpoint (backend offline)
# ---------------------------------------------------------------------------


class TestStatusEndpoint:
    def test_status_returns_valid_shape(self):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        # Relay always injects commandCount
        assert "commandCount" in data
        # runState should be a known value (or absent if error)
        if "runState" in data:
            assert data["runState"] in {"running", "stopped", "fault", "offline"}
