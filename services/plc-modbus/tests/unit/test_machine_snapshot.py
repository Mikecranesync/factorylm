"""Tests for the factorylm.machine-snapshot.v1 producer (MIRA PRD #3048, PR 2).

Two jobs:
1. Prove the envelope builder's behavior — state derivation, quality downgrade,
   fault/comms preservation, determinism, required-field refusal.
2. Prove wire compatibility against the SHARED fixtures in
   contracts/machine_snapshot/ (vendored verbatim from MIRA PR #3052): the
   valid fixture passes validate_envelope untouched, each invalid fixture
   fails for its documented reason, and this producer's output has the exact
   same shape as the golden payload.
"""

import json
import os
import subprocess
import sys

import pytest

from factorylm_plc.machine_snapshot import (
    PRODUCER,
    SCHEMA_VERSION,
    SOURCE_SYSTEM,
    VALID_QUALITIES,
    build_machine_snapshot_envelope,
    machine_state_from_snapshot,
    validate_envelope,
)
from factorylm_plc.models import TagSnapshot
from factorylm_plc.modbus_tag_source import REQUIRED_CANONICAL_TAGS

FIXTURES = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "contracts", "machine_snapshot"
)


def _snapshot(**overrides):
    base = dict(
        timestamp="2026-08-02T10:00:00Z",
        node_id="micro820-bench",
        motor_running=True,
        motor_speed=45,
        motor_current=3.2,
        temperature=41.5,
        pressure=0,
        conveyor_running=True,
        conveyor_speed=45,
        sensor_1=False,
        sensor_2=False,
        fault_alarm=False,
        e_stop=False,
        error_code=0,
        error_message="No error",
        io={"height_sensor_mm": 120, "sort_divert_active": False},
    )
    base.update(overrides)
    return TagSnapshot(**base)


def _envelope(snapshot=None, **overrides):
    kwargs = dict(
        tenant_id="staging",
        snapshot_id="snap-0001",
        gateway_id="edge-gateway-01",
        source_record_id="factorylm-conv-simple-01",
        proposed_uns_path="Enterprise/Site/Area/Line/conv_simple",
    )
    kwargs.update(overrides)
    return build_machine_snapshot_envelope(snapshot or _snapshot(), **kwargs)


def _load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


class TestMachineStateDerivation:
    def test_running(self):
        assert machine_state_from_snapshot(_snapshot()) == ("running", [])

    def test_stopped(self):
        snap = _snapshot(motor_running=False, conveyor_running=False)
        assert machine_state_from_snapshot(snap) == ("stopped", [])

    @pytest.mark.parametrize(
        "code,slug",
        [(1, "motor_overload"), (2, "temperature_high"), (3, "conveyor_jam"), (4, "sensor_failure")],
    )
    def test_faulted_carries_the_error_code_slug(self, code, slug):
        state, conditions = machine_state_from_snapshot(_snapshot(error_code=code, fault_alarm=True))
        assert state == "faulted"
        assert conditions == [slug]

    def test_fault_alarm_without_code(self):
        state, conditions = machine_state_from_snapshot(_snapshot(fault_alarm=True))
        assert (state, conditions) == ("faulted", ["fault_alarm"])

    def test_comm_loss_beats_fault(self):
        """A bridge that cannot talk to the PLC must not claim fault details
        beyond its own comm state."""
        state, conditions = machine_state_from_snapshot(_snapshot(error_code=5, fault_alarm=True))
        assert state == "comm_down"
        assert conditions == ["communication_loss"]

    def test_e_stop_is_an_active_condition(self):
        state, conditions = machine_state_from_snapshot(
            _snapshot(e_stop=True, motor_running=False, conveyor_running=False)
        )
        assert state == "estopped"
        assert "e_stop_active" in conditions

    def test_e_stop_beats_running(self):
        """An active E-stop must never be presented as a merely running
        machine (factorylm #203)."""
        state, conditions = machine_state_from_snapshot(
            _snapshot(e_stop=True, motor_running=True, conveyor_running=True, error_code=0)
        )
        assert state == "estopped"
        assert "e_stop_active" in conditions

    def test_comm_loss_still_beats_e_stop(self):
        """With the link down the bridge cannot vouch for E-stop either —
        comm_down stays dominant."""
        state, conditions = machine_state_from_snapshot(
            _snapshot(e_stop=True, error_code=5, fault_alarm=True)
        )
        assert state == "comm_down"
        assert "e_stop_active" in conditions


class TestEnvelopeBuilder:
    def test_healthy_envelope_is_valid_and_complete(self):
        env = _envelope()
        assert validate_envelope(env) == []
        assert env["schema_version"] == SCHEMA_VERSION
        assert env["source_system"] == SOURCE_SYSTEM
        assert env["provenance"]["producer"] == PRODUCER
        assert env["machine_state"] == "running"
        # every conv_simple canonical tag is present, all good, no clock use
        paths = {t["tag_path"] for t in env["tags"]}
        assert paths == {p for p in REQUIRED_CANONICAL_TAGS if p.startswith("conv_simple.")}
        assert all(t["quality"] == "good" for t in env["tags"])
        assert all(t["observed_at"] == "2026-08-02T10:00:00Z" for t in env["tags"])
        assert env["captured_at"] == "2026-08-02T10:00:00Z"

    def test_deterministic(self):
        assert _envelope() == _envelope()

    def test_comms_lost_preserves_fault_code_and_comm_ok_false(self):
        """PR 2 acceptance: 'A faulted/comms-lost snapshot preserves
        fault_code and comm_ok=false.'"""
        env = _envelope(_snapshot(error_code=5))
        assert validate_envelope(env) == []
        assert env["machine_state"] == "comm_down"
        by_path = {t["tag_path"]: t for t in env["tags"]}
        assert by_path["conv_simple.comm_ok"]["value"] is False
        assert by_path["conv_simple.fault_code"]["value"] == 5
        # bridge-known state stays good; unreachable measurements downgrade
        assert by_path["conv_simple.comm_ok"]["quality"] == "good"
        assert by_path["conv_simple.fault_code"]["quality"] == "good"
        assert by_path["conv_simple.vfd_speed_hz"]["quality"] == "uncertain"
        assert by_path["conv_simple.motor_run"]["quality"] == "uncertain"

    def test_never_upgrades_quality(self):
        for env in (_envelope(), _envelope(_snapshot(error_code=5))):
            assert {t["quality"] for t in env["tags"]} <= VALID_QUALITIES

    def test_tenant_id_is_never_defaulted(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _envelope(tenant_id="")

    def test_snapshot_id_required(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _envelope(snapshot_id="")

    def test_missing_source_timestamp_refuses_rather_than_inventing(self):
        with pytest.raises(ValueError, match="captured_at"):
            _envelope(_snapshot(timestamp=""))


class TestSharedFixtureCompatibility:
    def test_valid_fixture_passes_untouched(self):
        assert validate_envelope(_load_fixture("snapshot_v1_valid.json")) == []

    def test_producer_output_matches_golden_shape(self):
        """Same top-level keys, same tag paths, same tag-entry keys as the
        golden payload — semantic compatibility, not byte equality (values
        differ by machine state). Tag paths are compared as SETS against the
        canonical conv_simple.* tags so a dropped tag (factorylm #199) can
        never slip through a key-shape-only check again."""
        golden = _load_fixture("snapshot_v1_valid.json")
        mine = _envelope()
        assert set(mine) == set(golden)
        assert set(mine["asset"]) == set(golden["asset"])
        assert set(mine["provenance"]) == set(golden["provenance"])

        expected_paths = {p for p in REQUIRED_CANONICAL_TAGS if p.startswith("conv_simple.")}
        golden_paths = {t["tag_path"] for t in golden["tags"]}
        mine_paths = {t["tag_path"] for t in mine["tags"]}

        assert golden_paths == expected_paths
        assert mine_paths == golden_paths

        golden_tag_keys = {k for t in golden["tags"] for k in t}
        mine_tag_keys = {k for t in mine["tags"] for k in t}
        assert mine_tag_keys == golden_tag_keys

    @pytest.mark.parametrize(
        "name,reason",
        [
            ("snapshot_v1_invalid_missing_tenant.json", "tenant_id"),
            ("snapshot_v1_invalid_missing_timestamp.json", "captured_at"),
            ("snapshot_v1_invalid_schema_version.json", "schema_version"),
            ("snapshot_v1_invalid_malformed_tags.json", "tags["),
        ],
    )
    def test_invalid_fixtures_fail_for_their_documented_reason(self, name, reason):
        violations = validate_envelope(_load_fixture(name))
        assert violations, "%s should not validate" % name
        assert any(reason in v for v in violations), (name, violations)


class TestEnvelopeValidation:
    """validate_envelope enforces the real contract, not a subset of it
    (factorylm #201)."""

    def test_wrong_source_system_rejected(self):
        env = _envelope()
        env["source_system"] = "factorylm-plc-modbus"
        assert any("source_system" in v for v in validate_envelope(env))

    def test_noncanonical_tag_path_rejected(self):
        env = _envelope()
        env["tags"][0]["tag_path"] = "rogue.path"
        assert any("canonical" in v for v in validate_envelope(env))

    def test_stardust_canonical_paths_accepted(self):
        env = _envelope()
        env["tags"][0]["tag_path"] = "stardust.launch_1.block_occupied"
        assert validate_envelope(env) == []

    def test_unknown_quality_downgrades_not_rejects(self):
        """Per the PRD, unknown quality downgrades toward `uncertain` on the
        consumer side — the validator must not reject it."""
        env = _envelope()
        env["tags"][0]["quality"] = "banana"
        assert validate_envelope(env) == []


class TestObservationOnly:
    def test_module_is_pure_data_reshaping(self):
        """No Modbus, sockets, HTTP, or subprocess — the producer reshapes an
        already-read TagSnapshot and can never touch the plant."""
        import factorylm_plc.machine_snapshot as ms

        src = open(ms.__file__, encoding="utf-8").read()
        for forbidden in ("pymodbus", "socket", "requests", "urllib", "subprocess"):
            assert forbidden not in src, forbidden

    def test_import_path_is_fieldbus_free(self):
        """Importing factorylm_plc.machine_snapshot in a fresh interpreter
        must not drag in pymodbus or any hardware-facing module through the
        package __init__ (factorylm #202)."""
        code = (
            "import sys\n"
            "import factorylm_plc.machine_snapshot\n"
            "hardware = [m for m in sys.modules if 'pymodbus' in m]\n"
            "hardware += [m for m in sys.modules if m.startswith('factorylm_plc.') and\n"
            "             m.split('.')[-1] in ('modbus_client', 'micro820', 'factory_io',\n"
            "                                  'connection_manager', 'mock_plc', 'factory')]\n"
            "assert not hardware, hardware\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
        result = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr

    def test_lazy_exports_still_resolve(self):
        """`from factorylm_plc import create_plc_client` keeps working through
        the lazy __getattr__ (issue #202's compatibility requirement)."""
        import factorylm_plc

        assert callable(factorylm_plc.create_plc_client)
        assert callable(factorylm_plc.MockPLC)
        with pytest.raises(AttributeError):
            factorylm_plc.does_not_exist

    def test_command_shaped_fields_are_rejected(self):
        env = _envelope()
        env["tags"].append(
            {"tag_path": "conv_simple.motor_run", "value": True, "quality": "good",
             "observed_at": "2026-08-02T10:00:00Z", "write_command": 1}
        )
        assert any("forbidden" in v for v in validate_envelope(env))
