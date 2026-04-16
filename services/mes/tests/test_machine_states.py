"""Week 2 tests — machine state detection and transition logic.

All tests use unittest.mock — no live DB or plc-modbus required.
Run: pytest tests/test_machine_states.py -v

Acceptance Criteria (PRD-MES-CORE.md §10):
  AC#2  Machine state reads from live/mock PLC → tested via mocked fetch_io
  AC#4  Downtime event captured on fault within 10s → tested via transition logic
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.db_models import MachineStateEnum
from backend.services.plc_client import PLCOfflineError
from backend.services.state_machine import (
    ERROR_CODE_REASON_MAP,
    detect_state,
    is_transition,
    state_label,
)


# ── Fixtures: plc-modbus IO response shapes ───────────────────────────────────

def _io(vfd_status: int = 0, error_code: int = 0, item_count: int = 0) -> dict:
    """Build a minimal plc-modbus /api/plc/io response."""
    return {
        "coils":     {"Conveyor": vfd_status == 1, "RunCommand": False},
        "inputs":    {},
        "outputs":   {"DO_01": error_code == 7},
        "registers": {
            "ItemCount":       item_count,
            "ConveyorHz":      30 if vfd_status == 1 else 0,
            "MotorCurrentX10": 45 if vfd_status == 1 else 0,
            "MotorTempX10":    312,
            "VFDStatus":       vfd_status,
            "ErrorCode":       error_code,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── state_machine.detect_state ────────────────────────────────────────────────

class TestDetectState:
    def test_running_when_vfd_status_1(self):
        state, reason = detect_state(_io(vfd_status=1))
        assert state == MachineStateEnum.RUNNING
        assert reason is None

    def test_idle_when_vfd_status_0_no_error(self):
        state, reason = detect_state(_io(vfd_status=0, error_code=0))
        assert state == MachineStateEnum.IDLE
        assert reason is None

    def test_down_when_vfd_status_2(self):
        state, reason = detect_state(_io(vfd_status=2, error_code=0))
        assert state == MachineStateEnum.DOWN
        # No error code → UNKNOWN
        assert reason == "UNKNOWN"

    def test_down_with_error_code_takes_priority_over_running(self):
        # VFD still says running but fault flag set — fault wins
        state, reason = detect_state(_io(vfd_status=1, error_code=4))
        assert state == MachineStateEnum.DOWN
        assert reason == "JAM"

    def test_empty_io_defaults_to_idle(self):
        state, reason = detect_state({})
        assert state == MachineStateEnum.IDLE
        assert reason is None

    @pytest.mark.parametrize("error_code,expected_reason", [
        (1, "OVERLOAD"),
        (2, "OVERHEAT"),
        (3, "SENSOR_FAIL"),
        (4, "JAM"),
        (7, "E_STOP"),
        (99, "UNKNOWN"),   # unmapped → UNKNOWN
    ])
    def test_error_code_reason_mapping(self, error_code, expected_reason):
        state, reason = detect_state(_io(vfd_status=0, error_code=error_code))
        assert state == MachineStateEnum.DOWN
        assert reason == expected_reason

    def test_error_code_reason_map_completeness(self):
        """The 5 standard error codes must all be in the map."""
        assert set(ERROR_CODE_REASON_MAP.values()) == {
            "OVERLOAD", "OVERHEAT", "SENSOR_FAIL", "JAM", "E_STOP"
        }


# ── state_machine.is_transition ───────────────────────────────────────────────

class TestIsTransition:
    def test_none_current_always_transition(self):
        assert is_transition(None, MachineStateEnum.RUNNING) is True

    def test_same_state_no_transition(self):
        assert is_transition(MachineStateEnum.RUNNING, MachineStateEnum.RUNNING) is False

    def test_different_state_is_transition(self):
        assert is_transition(MachineStateEnum.RUNNING, MachineStateEnum.DOWN) is True
        assert is_transition(MachineStateEnum.IDLE, MachineStateEnum.OFFLINE) is True


# ── plc_client.fetch_io ───────────────────────────────────────────────────────

class TestPlcClient:
    @pytest.mark.asyncio
    async def test_fetch_io_returns_parsed_json(self):
        from backend.services.plc_client import fetch_io

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _io(vfd_status=1)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_io("http://plc-modbus:8001")

        assert result["registers"]["VFDStatus"] == 1

    @pytest.mark.asyncio
    async def test_fetch_io_raises_offline_on_connect_error(self):
        import httpx
        from backend.services.plc_client import PLCOfflineError, fetch_io

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("refused")
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(PLCOfflineError):
                await fetch_io("http://plc-modbus:8001")

    @pytest.mark.asyncio
    async def test_fetch_io_raises_offline_on_http_error(self):
        from backend.services.plc_client import PLCOfflineError, fetch_io

        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(PLCOfflineError):
                await fetch_io("http://plc-modbus:8001")


# ── state_poller (transition write logic) ────────────────────────────────────

class TestStatePollTransition:
    @pytest.mark.asyncio
    async def test_poll_line_detects_running_and_writes_transition(self):
        """When VFDStatus=1, poller should write RUNNING transition."""
        from backend.services import state_poller

        # Reset cache to simulate fresh start
        state_poller._state_cache.clear()

        mock_line = MagicMock()
        mock_line.id = "test-line-uuid"
        mock_line.name = "Conveyor-1"

        io_snapshot = _io(vfd_status=1)

        with patch(
            "backend.services.state_poller.fetch_io",
            new=AsyncMock(return_value=io_snapshot),
        ), patch(
            "backend.services.state_poller._apply_transition"
        ) as mock_apply:
            await state_poller._poll_line(mock_line)

        mock_apply.assert_called_once_with(
            "test-line-uuid", MachineStateEnum.RUNNING, None
        )
        assert state_poller._state_cache["test-line-uuid"] == MachineStateEnum.RUNNING

    @pytest.mark.asyncio
    async def test_poll_line_no_write_when_state_unchanged(self):
        """No DB write if state hasn't changed."""
        from backend.services import state_poller

        state_poller._state_cache["test-line-uuid2"] = MachineStateEnum.RUNNING

        mock_line = MagicMock()
        mock_line.id = "test-line-uuid2"
        mock_line.name = "Conveyor-1"

        io_snapshot = _io(vfd_status=1)  # still RUNNING

        with patch(
            "backend.services.state_poller.fetch_io",
            new=AsyncMock(return_value=io_snapshot),
        ), patch(
            "backend.services.state_poller._apply_transition"
        ) as mock_apply:
            await state_poller._poll_line(mock_line)

        mock_apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_line_writes_offline_on_plc_error(self):
        """PLCOfflineError → OFFLINE state written."""
        from backend.services import state_poller

        state_poller._state_cache.clear()

        mock_line = MagicMock()
        mock_line.id = "test-line-uuid3"
        mock_line.name = "Conveyor-1"

        with patch(
            "backend.services.state_poller.fetch_io",
            new=AsyncMock(side_effect=PLCOfflineError("timeout")),
        ), patch(
            "backend.services.state_poller._apply_transition"
        ) as mock_apply:
            await state_poller._poll_line(mock_line)

        mock_apply.assert_called_once_with(
            "test-line-uuid3", MachineStateEnum.OFFLINE, "COMMS_FAIL"
        )
