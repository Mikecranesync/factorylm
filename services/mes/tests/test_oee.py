"""Week 3 tests — OEE computation and calculator logic.

All tests use unittest.mock — no live DB or plc-modbus required.
Run: pytest tests/test_oee.py -v

Acceptance Criteria (PRD-MES-CORE.md §10):
  AC#3  OEE calculates correctly (known inputs → expected output ± 0.01)
  AC#5  TEEP reported alongside OEE
"""

import pytest
from backend.services.oee_calculator import (
    OEE_ALERT_TICKS,
    OEE_ALERT_THRESHOLD,
    _check_alert,
    _low_oee_ticks,
    compute_oee,
)


# ── compute_oee pure function ─────────────────────────────────────────────────

class TestComputeOEE:
    def test_perfect_oee(self):
        """100% on all three components → OEE = 1.0"""
        m = compute_oee(
            run_time_sec=60,
            planned_time_sec=60,
            total_count=60,
            good_count=60,
            ideal_cycle_sec=1.0,
        )
        assert m["availability"] == pytest.approx(1.0, abs=0.01)
        assert m["performance"]  == pytest.approx(1.0, abs=0.01)
        assert m["quality"]      == pytest.approx(1.0, abs=0.01)
        assert m["oee"]          == pytest.approx(1.0, abs=0.01)

    def test_typical_factory_oee(self):
        """Walker Reynolds benchmark: typical factory ~55% OEE.

        Inputs:
          planned=60s, run=48s → A=0.80
          count=40 @ 1s/part, run=48s → P=40/48=0.833
          good=38/40 → Q=0.95
          OEE = 0.80 × 0.833 × 0.95 ≈ 0.633
        """
        m = compute_oee(
            run_time_sec=48,
            planned_time_sec=60,
            total_count=40,
            good_count=38,
            ideal_cycle_sec=1.0,
        )
        assert m["availability"] == pytest.approx(0.80,  abs=0.01)
        assert m["performance"]  == pytest.approx(0.833, abs=0.01)
        assert m["quality"]      == pytest.approx(0.95,  abs=0.01)
        assert m["oee"]          == pytest.approx(0.633, abs=0.01)
        assert "teep" in m

    def test_zero_planned_time_returns_zeros(self):
        """OFFLINE line — planned_time=0 → all zeros, no division error."""
        m = compute_oee(
            run_time_sec=0,
            planned_time_sec=0,
            total_count=0,
            good_count=0,
            ideal_cycle_sec=1.0,
        )
        assert m["oee"] == 0.0
        assert m["availability"] == 0.0

    def test_zero_count_returns_zero_performance_and_quality(self):
        """Line running but no parts produced — P and Q are 0."""
        m = compute_oee(
            run_time_sec=60,
            planned_time_sec=60,
            total_count=0,
            good_count=0,
            ideal_cycle_sec=1.0,
        )
        assert m["availability"] == pytest.approx(1.0, abs=0.01)
        assert m["performance"]  == 0.0
        assert m["quality"]      == 0.0
        assert m["oee"]          == 0.0

    def test_performance_clamped_to_1(self):
        """Items produced faster than ideal → Performance capped at 1.0."""
        m = compute_oee(
            run_time_sec=60,
            planned_time_sec=60,
            total_count=120,   # twice the ideal rate
            good_count=120,
            ideal_cycle_sec=1.0,
        )
        assert m["performance"] == pytest.approx(1.0, abs=0.01)
        assert m["oee"]         == pytest.approx(1.0, abs=0.01)

    def test_availability_clamped_to_1(self):
        """run_time > planned_time (clock skew) → clamped to 1.0."""
        m = compute_oee(
            run_time_sec=65,
            planned_time_sec=60,
            total_count=60,
            good_count=60,
            ideal_cycle_sec=1.0,
        )
        assert m["availability"] == pytest.approx(1.0, abs=0.01)

    def test_teep_equals_oee_without_schedule(self):
        """Until schedules are wired (Week 4), TEEP == OEE."""
        m = compute_oee(60, 60, 60, 60, 1.0)
        assert m["teep"] == pytest.approx(m["oee"], abs=0.001)

    def test_slow_cycle_reduces_performance(self):
        """Ideal=1s, actual=2s/part → P=0.5"""
        m = compute_oee(
            run_time_sec=60,
            planned_time_sec=60,
            total_count=30,   # 30 parts in 60s = 2s/part
            good_count=30,
            ideal_cycle_sec=1.0,
        )
        assert m["performance"] == pytest.approx(0.50, abs=0.01)
        assert m["oee"]         == pytest.approx(0.50, abs=0.01)

    def test_world_class_oee_benchmark(self):
        """Walker benchmark: world-class ≥ 85%"""
        m = compute_oee(
            run_time_sec=55,
            planned_time_sec=60,
            total_count=54,
            good_count=54,
            ideal_cycle_sec=1.0,
        )
        assert m["oee"] >= 0.85

    def test_output_rounded_to_4_decimals(self):
        m = compute_oee(48, 60, 40, 38, 1.0)
        for key in ["availability", "performance", "quality", "oee", "teep"]:
            val = m[key]
            assert val == round(val, 4), f"{key} not rounded: {val}"


# ── Alert logic ───────────────────────────────────────────────────────────────

class TestAlertLogic:
    def setup_method(self):
        _low_oee_ticks.clear()

    def test_counter_increments_below_threshold(self):
        _check_alert("Line-1", "lid1", OEE_ALERT_THRESHOLD - 0.01)
        assert _low_oee_ticks["lid1"] == 1

    def test_counter_resets_above_threshold(self):
        _low_oee_ticks["lid2"] = 10
        _check_alert("Line-2", "lid2", OEE_ALERT_THRESHOLD + 0.01)
        assert _low_oee_ticks["lid2"] == 0

    def test_alert_fires_at_threshold_tick(self, caplog):
        import logging
        _low_oee_ticks["lid3"] = OEE_ALERT_TICKS - 1
        with caplog.at_level(logging.WARNING):
            _check_alert("Line-3", "lid3", 0.40)
        assert "ALERT" in caplog.text
        assert _low_oee_ticks["lid3"] == OEE_ALERT_TICKS

    def test_no_alert_before_threshold_tick(self, caplog):
        import logging
        _low_oee_ticks["lid4"] = OEE_ALERT_TICKS - 2
        with caplog.at_level(logging.WARNING):
            _check_alert("Line-4", "lid4", 0.40)
        assert "ALERT" not in caplog.text


# ── OEE Threshold constants ───────────────────────────────────────────────────

class TestConstants:
    def test_alert_threshold_is_60_percent(self):
        assert OEE_ALERT_THRESHOLD == 0.60

    def test_alert_ticks_is_30(self):
        """30 ticks × 60s = 30 minutes before alert fires."""
        assert OEE_ALERT_TICKS == 30
