"""
CI Tests for Telegram Emulator
==============================
Run with: pytest tests/test_telegram_emulator.py -v
"""

import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.telegram_emulator import TelegramEmulator, MockUpdate, MockMessage


class TestMockObjects:
    """Test mock Telegram objects."""

    def test_mock_message_create(self):
        msg = MockMessage.create("Hello world")
        assert msg.text == "Hello world"
        assert msg.from_user.username == "test_technician"
        assert msg.chat.type == "private"

    def test_mock_update_create(self):
        update = MockUpdate.create("Test message")
        assert update.message.text == "Test message"
        assert update.update_id > 0


class TestEmulatorRouting:
    """Test message routing logic."""

    @pytest.fixture
    def emulator(self):
        return TelegramEmulator(verbose=False)

    def test_start_command(self, emulator):
        response = emulator.send_message("/start")
        assert "Welcome" in response.text
        assert "FactoryLM" in response.text

    def test_help_command(self, emulator):
        response = emulator.send_message("/help")
        assert "Commands" in response.text
        assert "show me IO" in response.text

    def test_show_io_routing(self, emulator):
        # These should all route to show_io handler
        for msg in ["show me IO", "show io", "live io", "plc io"]:
            response = emulator.send_message(msg)
            # Should either show data or connection error, not "didn't understand"
            assert "didn't understand" not in response.text.lower()

    def test_diagnosis_routing(self, emulator):
        # These should all route to diagnosis handler
        for msg in ["why is this stopped", "diagnose", "what's wrong", "any faults"]:
            response = emulator.send_message(msg)
            assert "didn't understand" not in response.text.lower()

    def test_unknown_message(self, emulator):
        response = emulator.send_message("xyzzy foobar gibberish")
        assert "didn't understand" in response.text.lower() or "Try" in response.text

    def test_conversation_history(self, emulator):
        emulator.send_message("/start")
        emulator.send_message("show io")

        assert len(emulator.conversation_history) == 4  # 2 user + 2 bot
        assert emulator.conversation_history[0]["role"] == "user"
        assert emulator.conversation_history[1]["role"] == "bot"


class TestLiveIntegration:
    """
    Integration tests that require live services.
    Skip if Matrix API is not available.
    """

    @pytest.fixture
    def emulator(self):
        return TelegramEmulator(
            matrix_url=os.getenv("MATRIX_URL", "http://100.72.2.99:8000"),
            verbose=False
        )

    @pytest.fixture
    def live_services(self, emulator):
        """Skip if Matrix API is not reachable."""
        import httpx
        try:
            resp = httpx.get(f"{emulator.matrix_url}/api/health", timeout=5)
            if resp.status_code != 200:
                pytest.skip("Matrix API not healthy")
        except Exception:
            pytest.skip("Matrix API not reachable")

    def test_live_show_io(self, emulator, live_services):
        response = emulator.send_message("show me IO")
        assert "Motor" in response.text
        assert "Conveyor" in response.text
        assert response.latency_ms < 10000

    def test_live_status_check(self, emulator, live_services):
        response = emulator.send_message("/status")
        assert "Matrix API" in response.text


class TestScriptRunner:
    """Test scripted conversation playback."""

    def test_script_file_loading(self, tmp_path):
        # Create a simple test script
        script = {
            "name": "Simple Test",
            "steps": [
                {"user": "/start", "expect_contains": ["Welcome"]}
            ]
        }

        script_file = tmp_path / "test_script.json"
        import json
        script_file.write_text(json.dumps(script))

        emulator = TelegramEmulator(verbose=False)
        results = emulator.run_script(str(script_file))

        assert results["name"] == "Simple Test"
        assert results["passed"] >= 0
        assert len(results["steps"]) == 1


# ============================================================================
# Run maintenance flow test
# ============================================================================

@pytest.mark.integration
def test_maintenance_flow():
    """
    Full integration test of maintenance workflow.
    Requires live Matrix API.
    """
    import httpx

    matrix_url = os.getenv("MATRIX_URL", "http://100.72.2.99:8000")

    # Check if Matrix API is available
    try:
        resp = httpx.get(f"{matrix_url}/api/health", timeout=5)
        if resp.status_code != 200:
            pytest.skip("Matrix API not healthy")
    except Exception:
        pytest.skip("Matrix API not reachable")

    # Run the maintenance flow script
    script_path = Path(__file__).parent / "conversations" / "maintenance_flow.json"
    if not script_path.exists():
        pytest.skip("Maintenance flow script not found")

    emulator = TelegramEmulator(matrix_url=matrix_url, verbose=True)
    results = emulator.run_script(str(script_path))

    assert results["failed"] == 0, f"Failed steps: {[s for s in results['steps'] if not s['passed']]}"
