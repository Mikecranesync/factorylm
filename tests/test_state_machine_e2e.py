"""E2E tests for OpenClaw state machine — runs against live VPS.

Requires VPS at 100.68.120.99 with OpenClaw running.
Run with: python3 tests/test_state_machine_e2e.py
"""

import json
import sys
import unittest
import urllib.request
import urllib.error

VPS_BASE = "http://100.68.120.99:8340"


def _get(path: str, timeout: int = 10) -> dict:
    """GET a JSON endpoint from the VPS."""
    url = f"{VPS_BASE}{path}"
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode())


class TestHealthReturnsState(unittest.TestCase):
    """E2E-1: GET /health includes state + capabilities."""

    def test_health_returns_state(self):
        data = _get("/health")
        self.assertIn("state", data, "/health response must include 'state'")
        self.assertIn("capabilities", data, "/health response must include 'capabilities'")
        self.assertIn(data["state"], ["booting", "healthy", "degraded", "critical"])


class TestRootIncludesState(unittest.TestCase):
    """E2E-2: GET / includes state field."""

    def test_root_includes_state(self):
        data = _get("/")
        self.assertIn("state", data, "/ response must include 'state'")
        self.assertIn(data["state"], ["booting", "healthy", "degraded", "critical"])


class TestAllCapabilitiesListed(unittest.TestCase):
    """E2E-3: Health response lists expected capabilities."""

    # These are the capabilities we expect to be registered
    EXPECTED_CAPS = {
        "llm_primary",  # critical — at least one LLM
        "tts",          # voice synthesis
        "gh_cli",       # GitHub CLI
        "budget",       # budget tracker
    }

    def test_all_capabilities_listed(self):
        data = _get("/health")
        caps = set(data.get("capabilities", {}).keys())
        for expected in self.EXPECTED_CAPS:
            self.assertIn(expected, caps, f"Missing capability: {expected}")
        # Should have at least 5 capabilities (LLM providers + the above)
        self.assertGreaterEqual(len(caps), 5, f"Only {len(caps)} capabilities registered: {caps}")


class TestStateIsHealthyOnFreshBoot(unittest.TestCase):
    """E2E-4: After restart, state is healthy (or degraded with known gaps)."""

    def test_state_is_not_critical(self):
        data = _get("/health")
        state = data["state"]
        # On a fresh boot with valid keys, should be healthy or degraded (never critical)
        self.assertIn(state, ["healthy", "degraded"],
                      f"Bot is in {state} state — expected healthy or degraded")
        if state == "degraded":
            degraded = [
                name for name, info in data["capabilities"].items()
                if info["status"] == "down"
            ]
            print(f"  [INFO] DEGRADED with down capabilities: {degraded}")


class TestApiRespondsNormally(unittest.TestCase):
    """E2E-5: POST /api/message gets a response (no spurious warnings when healthy)."""

    def test_api_responds(self):
        url = f"{VPS_BASE}/api/v1/message"
        body = json.dumps({
            "user_id": "test-e2e",
            "text": "hello",
        }).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.loads(resp.read().decode())
            self.assertIn("text", data, "API response must include 'text'")
            # If state is healthy, response should NOT contain degradation warnings
            health = _get("/health")
            if health["state"] == "healthy":
                self.assertNotIn("temporarily unavailable", data["text"],
                                "Healthy bot should not append degradation warnings")
        except urllib.error.HTTPError as e:
            self.fail(f"API returned HTTP {e.code}: {e.read().decode()}")


if __name__ == "__main__":
    # Run tests and print results
    print(f"Testing OpenClaw state machine E2E against {VPS_BASE}")
    print("=" * 60)
    unittest.main(verbosity=2)
