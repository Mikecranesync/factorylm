"""Regression tests for backend API models — issue #161.

RegisterData declared placeholder fields (register_101..105) while
plc_connection.read_io() produces the NAMED VFD fields from REGISTER_NAMES.
Pydantic v2 silently drops unknown fields, so every named value was stripped
from /api/plc/io and replaced with the 0 default — diagnosis read zeros while
the PLC reported real data.

These tests pin the model to the source of truth so the two cannot drift
apart silently again.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.plc_models import RegisterData  # noqa: E402

_PLC_CONNECTION = os.path.join(
    os.path.dirname(__file__), "..", "..", "backend", "services", "plc_connection.py"
)


def _register_names_from_source():
    """REGISTER_NAMES parsed from plc_connection.py's source.

    Parsed rather than imported: importing plc_connection pulls in pymodbus,
    which this pure-model test must not depend on. The dict literal is the
    source of truth read_io() builds its response from.
    """
    with open(_PLC_CONNECTION, encoding="utf-8") as fh:
        src = fh.read()
    block = re.search(r"REGISTER_NAMES\s*=\s*\{(.*?)\}", src, re.DOTALL)
    assert block, "REGISTER_NAMES not found in plc_connection.py"
    names = re.findall(r'\d+\s*:\s*"([A-Za-z0-9_]+)"', block.group(1))
    assert names, "REGISTER_NAMES parsed empty"
    return names


class TestRegisterDataMatchesSource:
    def test_model_fields_equal_register_names(self):
        """The model accepts exactly the names read_io() produces — no
        placeholders, nothing dropped, nothing extra."""
        expected = set(_register_names_from_source())
        actual = set(RegisterData.model_fields)
        assert actual == expected, (
            "RegisterData fields %s != REGISTER_NAMES %s — Pydantic v2 drops "
            "unknown fields, so any mismatch silently zeroes telemetry (#161)"
            % (sorted(actual), sorted(expected))
        )

    def test_named_vfd_values_survive_round_trip(self):
        """The exact dict shape read_io() emits keeps its values."""
        payload = {
            "ItemCount": 42,
            "ConveyorHz": 583,
            "MotorCurrentX10": 27,
            "MotorTempX10": 415,
            "VFDStatus": 2,
            "ErrorCode": 0,
        }
        model = RegisterData(**payload)
        assert model.model_dump() == payload

    def test_no_placeholder_fields_remain(self):
        for field in RegisterData.model_fields:
            assert not field.startswith("register_"), (
                "placeholder field %r reintroduced — this is the #161 bug" % field
            )
