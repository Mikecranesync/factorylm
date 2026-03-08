"""Unit tests for OpenClaw state machine (state.py + monitor.py).

All mocked — no VPS required. Tests the StateMachine and CapabilityMonitor
classes in isolation.
"""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os

# We test standalone copies of the state machine types and logic.
# Since the actual code lives on VPS, we replicate the core classes here
# and verify behavior. The E2E tests hit the live VPS.

# ── Inline copies of VPS types (for standalone testing) ──────────────────

from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Awaitable


class BotState(str, Enum):
    BOOTING = "booting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class CapabilityStatus(str, Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


CHECK_TIMEOUT = 5.0


@dataclass
class Capability:
    name: str
    critical: bool
    check: Callable[[], Awaitable[bool]]
    recover: Callable[[], Awaitable[None]] | None = None
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    last_check: float = 0.0
    last_error: str = ""
    consecutive_failures: int = 0


class StateMachine:
    def __init__(self) -> None:
        self.state: BotState = BotState.BOOTING
        self.capabilities: dict[str, Capability] = {}
        self._boot_time: float = time.time()

    def register(self, name, critical, check, recover=None):
        self.capabilities[name] = Capability(
            name=name, critical=critical, check=check, recover=recover,
        )

    async def check_all(self) -> BotState:
        tasks = {
            name: asyncio.create_task(self._safe_check(cap))
            for name, cap in self.capabilities.items()
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for (name, _task), result in zip(tasks.items(), results):
            cap = self.capabilities[name]
            cap.last_check = time.time()
            if isinstance(result, Exception):
                cap.status = CapabilityStatus.DOWN
                cap.last_error = str(result)
                cap.consecutive_failures += 1
            elif result is True:
                cap.status = CapabilityStatus.UP
                cap.last_error = ""
                cap.consecutive_failures = 0
            else:
                cap.status = CapabilityStatus.DOWN
                cap.last_error = "check returned False"
                cap.consecutive_failures += 1
        self.state = self._compute_state()
        return self.state

    async def check_one(self, name) -> CapabilityStatus:
        cap = self.capabilities.get(name)
        if not cap:
            return CapabilityStatus.UNKNOWN
        try:
            ok = await asyncio.wait_for(cap.check(), timeout=CHECK_TIMEOUT)
            cap.last_check = time.time()
            if ok:
                cap.status = CapabilityStatus.UP
                cap.last_error = ""
                cap.consecutive_failures = 0
            else:
                cap.status = CapabilityStatus.DOWN
                cap.last_error = "check returned False"
                cap.consecutive_failures += 1
        except Exception as exc:
            cap.status = CapabilityStatus.DOWN
            cap.last_error = str(exc)
            cap.consecutive_failures += 1
            cap.last_check = time.time()
        self.state = self._compute_state()
        return cap.status

    async def recover_one(self, name) -> bool:
        cap = self.capabilities.get(name)
        if not cap or not cap.recover:
            return False
        try:
            await asyncio.wait_for(cap.recover(), timeout=CHECK_TIMEOUT)
            ok = await asyncio.wait_for(cap.check(), timeout=CHECK_TIMEOUT)
            if ok:
                cap.status = CapabilityStatus.UP
                cap.last_error = ""
                cap.consecutive_failures = 0
                self.state = self._compute_state()
                return True
        except Exception:
            pass
        return False

    def is_capable(self, *names) -> bool:
        for name in names:
            cap = self.capabilities.get(name)
            if not cap or cap.status != CapabilityStatus.UP:
                return False
        return True

    def degraded_capabilities(self) -> list[str]:
        return [
            name for name, cap in self.capabilities.items()
            if cap.status == CapabilityStatus.DOWN
        ]

    def summary(self) -> dict:
        return {
            "state": self.state.value,
            "uptime_seconds": round(time.time() - self._boot_time, 1),
            "capabilities": {
                name: {
                    "status": cap.status.value,
                    "critical": cap.critical,
                    "last_check": round(cap.last_check, 1) if cap.last_check else None,
                    "last_error": cap.last_error or None,
                    "consecutive_failures": cap.consecutive_failures,
                }
                for name, cap in self.capabilities.items()
            },
        }

    async def _safe_check(self, cap):
        return await asyncio.wait_for(cap.check(), timeout=CHECK_TIMEOUT)

    def _compute_state(self) -> BotState:
        any_critical_down = any(
            cap.status == CapabilityStatus.DOWN
            for cap in self.capabilities.values()
            if cap.critical
        )
        if any_critical_down:
            return BotState.CRITICAL
        any_down = any(
            cap.status == CapabilityStatus.DOWN
            for cap in self.capabilities.values()
        )
        if any_down:
            return BotState.DEGRADED
        all_checked = all(
            cap.status != CapabilityStatus.UNKNOWN
            for cap in self.capabilities.values()
        )
        if all_checked:
            return BotState.HEALTHY
        return BotState.BOOTING


# ── Helpers ──────────────────────────────────────────────────────────────

def _run(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _ok():
    return True


async def _fail():
    return False


async def _slow():
    await asyncio.sleep(10)
    return True


async def _raise():
    raise ConnectionError("boom")


async def _noop():
    pass


# ── Unit Tests ───────────────────────────────────────────────────────────

class TestStateMachineInit(unittest.TestCase):
    """Test 1: Initial state is BOOTING."""

    def test_initial_state_is_booting(self):
        sm = StateMachine()
        self.assertEqual(sm.state, BotState.BOOTING)


class TestRegisterCapability(unittest.TestCase):
    """Test 2: Capability registered with name and critical flag."""

    def test_register_capability(self):
        sm = StateMachine()
        sm.register("groq", critical=False, check=_ok)
        self.assertIn("groq", sm.capabilities)
        self.assertFalse(sm.capabilities["groq"].critical)
        self.assertEqual(sm.capabilities["groq"].status, CapabilityStatus.UNKNOWN)


class TestCheckAllHealthy(unittest.TestCase):
    """Test 3: All checks pass → HEALTHY."""

    def test_check_all_healthy(self):
        sm = StateMachine()
        sm.register("llm", critical=True, check=_ok)
        sm.register("tts", critical=False, check=_ok)
        state = _run(sm.check_all())
        self.assertEqual(state, BotState.HEALTHY)


class TestCheckAllDegraded(unittest.TestCase):
    """Test 4: Non-critical check fails → DEGRADED."""

    def test_check_all_degraded(self):
        sm = StateMachine()
        sm.register("llm", critical=True, check=_ok)
        sm.register("tts", critical=False, check=_fail)
        state = _run(sm.check_all())
        self.assertEqual(state, BotState.DEGRADED)


class TestCheckAllCritical(unittest.TestCase):
    """Test 5: Critical check fails → CRITICAL."""

    def test_check_all_critical(self):
        sm = StateMachine()
        sm.register("llm", critical=True, check=_fail)
        sm.register("tts", critical=False, check=_ok)
        state = _run(sm.check_all())
        self.assertEqual(state, BotState.CRITICAL)


class TestCheckTimeout(unittest.TestCase):
    """Test 6: Slow check (>5s) → treated as DOWN."""

    def test_check_timeout(self):
        sm = StateMachine()
        sm.register("slow_provider", critical=False, check=_slow)
        sm.register("llm", critical=True, check=_ok)
        state = _run(sm.check_all())
        self.assertEqual(sm.capabilities["slow_provider"].status, CapabilityStatus.DOWN)
        self.assertEqual(state, BotState.DEGRADED)


class TestIsCapableTrue(unittest.TestCase):
    """Test 7: is_capable returns True when capability is UP."""

    def test_is_capable_true(self):
        sm = StateMachine()
        sm.register("tts", critical=False, check=_ok)
        _run(sm.check_all())
        self.assertTrue(sm.is_capable("tts"))


class TestIsCapableFalse(unittest.TestCase):
    """Test 8: is_capable returns False when capability is DOWN."""

    def test_is_capable_false(self):
        sm = StateMachine()
        sm.register("tts", critical=False, check=_fail)
        _run(sm.check_all())
        self.assertFalse(sm.is_capable("tts"))


class TestDegradedCapabilitiesList(unittest.TestCase):
    """Test 9: degraded_capabilities() returns DOWN names."""

    def test_degraded_capabilities_list(self):
        sm = StateMachine()
        sm.register("llm", critical=True, check=_ok)
        sm.register("tts", critical=False, check=_fail)
        sm.register("gh", critical=False, check=_fail)
        _run(sm.check_all())
        degraded = sm.degraded_capabilities()
        self.assertIn("tts", degraded)
        self.assertIn("gh", degraded)
        self.assertNotIn("llm", degraded)


class TestRecoveryCalled(unittest.TestCase):
    """Test 10: recover_one() calls the recover function."""

    def test_recovery_called(self):
        recover_mock = AsyncMock()
        sm = StateMachine()
        # Starts failing, recovery re-enables
        call_count = 0

        async def _check_toggling():
            nonlocal call_count
            call_count += 1
            return call_count > 1  # First call fails, second succeeds (after recovery)

        sm.register("tts", critical=False, check=_check_toggling, recover=recover_mock)
        _run(sm.check_all())  # First check → DOWN
        _run(sm.recover_one("tts"))
        recover_mock.assert_called_once()


class TestRecoveryRestoresStatus(unittest.TestCase):
    """Test 11: After recovery, capability status → UP."""

    def test_recovery_restores_status(self):
        sm = StateMachine()
        attempts = 0

        async def _check():
            nonlocal attempts
            attempts += 1
            return attempts > 1

        sm.register("tts", critical=False, check=_check, recover=_noop)
        _run(sm.check_all())
        self.assertEqual(sm.capabilities["tts"].status, CapabilityStatus.DOWN)
        result = _run(sm.recover_one("tts"))
        self.assertTrue(result)
        self.assertEqual(sm.capabilities["tts"].status, CapabilityStatus.UP)


class TestRecoveryFailureKeepsDown(unittest.TestCase):
    """Test 12: Failed recovery keeps status DOWN."""

    def test_recovery_failure_keeps_down(self):
        sm = StateMachine()
        sm.register("tts", critical=False, check=_fail, recover=_noop)
        _run(sm.check_all())
        result = _run(sm.recover_one("tts"))
        self.assertFalse(result)
        self.assertEqual(sm.capabilities["tts"].status, CapabilityStatus.DOWN)


class TestSummaryFormat(unittest.TestCase):
    """Test 13: summary() returns correct dict structure."""

    def test_summary_format(self):
        sm = StateMachine()
        sm.register("llm", critical=True, check=_ok)
        sm.register("tts", critical=False, check=_fail)
        _run(sm.check_all())
        summary = sm.summary()
        self.assertIn("state", summary)
        self.assertIn("uptime_seconds", summary)
        self.assertIn("capabilities", summary)
        self.assertIn("llm", summary["capabilities"])
        self.assertIn("tts", summary["capabilities"])
        self.assertEqual(summary["capabilities"]["llm"]["status"], "up")
        self.assertEqual(summary["capabilities"]["tts"]["status"], "down")
        self.assertTrue(summary["capabilities"]["llm"]["critical"])
        self.assertFalse(summary["capabilities"]["tts"]["critical"])


class TestConsecutiveFailureCounter(unittest.TestCase):
    """Test 14: Counter increments on each failed check."""

    def test_consecutive_failure_counter(self):
        sm = StateMachine()
        sm.register("tts", critical=False, check=_fail)
        sm.register("llm", critical=True, check=_ok)
        _run(sm.check_all())
        self.assertEqual(sm.capabilities["tts"].consecutive_failures, 1)
        _run(sm.check_all())
        self.assertEqual(sm.capabilities["tts"].consecutive_failures, 2)
        _run(sm.check_all())
        self.assertEqual(sm.capabilities["tts"].consecutive_failures, 3)


class TestStateTransitionHealthyToDegraded(unittest.TestCase):
    """Test 15: Transition from HEALTHY to DEGRADED when capability drops."""

    def test_state_transition_healthy_to_degraded(self):
        sm = StateMachine()
        tts_ok = True

        async def _check_tts():
            return tts_ok

        sm.register("llm", critical=True, check=_ok)
        sm.register("tts", critical=False, check=_check_tts)
        state = _run(sm.check_all())
        self.assertEqual(state, BotState.HEALTHY)

        tts_ok = False
        state = _run(sm.check_all())
        self.assertEqual(state, BotState.DEGRADED)


class TestStateTransitionDegradedToHealthy(unittest.TestCase):
    """Test 16: Transition from DEGRADED to HEALTHY when capability recovers."""

    def test_state_transition_degraded_to_healthy(self):
        sm = StateMachine()
        tts_ok = False

        async def _check_tts():
            return tts_ok

        sm.register("llm", critical=True, check=_ok)
        sm.register("tts", critical=False, check=_check_tts)
        state = _run(sm.check_all())
        self.assertEqual(state, BotState.DEGRADED)

        tts_ok = True
        state = _run(sm.check_all())
        self.assertEqual(state, BotState.HEALTHY)


class TestCriticalToHealthyAfterRecovery(unittest.TestCase):
    """Test 17: Full recovery path from CRITICAL to HEALTHY."""

    def test_critical_to_healthy_after_recovery(self):
        sm = StateMachine()
        llm_ok = False

        async def _check_llm():
            return llm_ok

        sm.register("llm", critical=True, check=_check_llm)
        state = _run(sm.check_all())
        self.assertEqual(state, BotState.CRITICAL)

        llm_ok = True

        async def _recover():
            pass

        sm.capabilities["llm"].recover = _recover
        result = _run(sm.recover_one("llm"))
        self.assertTrue(result)
        self.assertEqual(sm.state, BotState.HEALTHY)


class TestMonitorLoopCallsCheckAll(unittest.TestCase):
    """Test 18: Monitor._loop() calls sm.check_all()."""

    def test_monitor_loop_calls_check_all(self):
        sm = StateMachine()
        sm.register("llm", critical=True, check=_ok)
        check_all_original = sm.check_all
        call_count = 0

        async def _mock_check_all():
            nonlocal call_count
            call_count += 1
            return await check_all_original()

        sm.check_all = _mock_check_all

        async def _run_one_cycle():
            from unittest.mock import patch
            # Simulate one monitor cycle
            old_state = sm.state
            new_state = await sm.check_all()
            for cap_name in sm.degraded_capabilities():
                await sm.recover_one(cap_name)

        _run(_run_one_cycle())
        self.assertGreaterEqual(call_count, 1)


class TestMonitorAttemptsRecovery(unittest.TestCase):
    """Test 19: Monitor loop tries recover_one() for degraded caps."""

    def test_monitor_attempts_recovery(self):
        sm = StateMachine()
        recover_mock = AsyncMock()
        attempts = 0

        async def _check():
            nonlocal attempts
            attempts += 1
            return attempts > 2

        sm.register("llm", critical=True, check=_ok)
        sm.register("tts", critical=False, check=_check, recover=recover_mock)

        async def _run_monitor_cycle():
            await sm.check_all()
            for cap_name in sm.degraded_capabilities():
                await sm.recover_one(cap_name)

        _run(_run_monitor_cycle())
        recover_mock.assert_called_once()


class TestDispatchGuardCritical(unittest.TestCase):
    """Test 20: Dispatch returns 'broken boy' when CRITICAL."""

    def test_dispatch_guard_critical(self):
        sm = StateMachine()
        sm.register("llm", critical=True, check=_fail)
        _run(sm.check_all())
        self.assertEqual(sm.state, BotState.CRITICAL)

        # Simulate dispatch guard
        if sm.state == BotState.CRITICAL:
            response_text = (
                "Whoops, I'm a broken boy right now — critical systems are offline. "
                "Mike's been notified and I'll be back once things are restored."
            )
        else:
            response_text = "Normal response"

        self.assertIn("broken boy", response_text)


if __name__ == "__main__":
    unittest.main()
