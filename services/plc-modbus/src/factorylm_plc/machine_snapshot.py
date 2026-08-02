"""Produce `factorylm.machine-snapshot.v1` envelopes from canonical PLC tags.

PR 2 of the MIRA machine-evidence handoff (MIRA PRD
`docs/prd/2026-08-01-mira-factorylm-machine-evidence-handoff.md`, tracked on
MIRA #3048). The envelope is the compatibility boundary between FactoryLM
(producer, this module) and MIRA (consumer,
`materialized_evidence.context_contract`). Both repositories test against the
SAME fixtures in `contracts/machine_snapshot/` — vendored verbatim from MIRA
PR #3052; neither side changes a fixture without re-running the other side's
tests.

Contract rules honored here (PRD § "Contract rules"):

- `schema_version`, `snapshot_id`, `captured_at`, `tenant_id`, `tags` required.
- `source_system` is `plc_bridge` — NOT "factorylm-plc-modbus", which MIRA's
  ingest rejects (`VALID_SOURCE_SYSTEMS`). The FactoryLM identity rides in
  `provenance.producer` instead. (PRD amendment 2026-08-02.)
- `tenant_id` is never defaulted or inferred: the caller must supply it, and a
  falsy value raises.
- `captured_at`/`observed_at` come from the snapshot's own timestamp — freshness
  is never invented with now().
- `tag_path` values are the canonical names from `REQUIRED_CANONICAL_TAGS`
  (modbus_tag_source) — never raw register numbers.
- `quality` uses MIRA's ingest vocabulary {good, bad, stale, uncertain} and
  only ever downgrades toward less confidence.
- Observation data only: no command, write, actuator, or control field exists
  anywhere in this module, and it imports no Modbus/network machinery — it is
  pure data reshaping over an already-read `TagSnapshot`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .models import ERROR_CODES, TagSnapshot
from .modbus_tag_source import (
    REQUIRED_CANONICAL_TAGS,
    canonical_tags_from_snapshot,
    unsourced_canonical_tags,
)

SCHEMA_VERSION = "factorylm.machine-snapshot.v1"
SOURCE_SYSTEM = "plc_bridge"
PRODUCER = "factorylm-plc-modbus"

VALID_QUALITIES = frozenset({"good", "bad", "stale", "uncertain"})

# The Micro820 bridge reports communication loss as error code 5 — the same
# convention canonical_tags_from_snapshot uses for conv_simple.comm_ok.
COMM_LOSS_ERROR_CODE = 5

# Fields that would make the payload something other than pure observation.
# validate_envelope rejects any of these at any depth (PRD: "No command,
# write, actuator, or control field is permitted").
FORBIDDEN_FIELD_TOKENS = ("command", "write", "actuate", "setpoint_write", "control")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def machine_state_from_snapshot(snapshot: TagSnapshot) -> Tuple[str, List[str]]:
    """Derive (machine_state, active_conditions) deterministically.

    Precedence: communication loss beats e-stop beats fault beats running — a
    bridge that cannot talk to the PLC does not know the motor is running, so
    it must not claim it, and an active E-stop can never be presented as a
    merely running machine. States use MIRA's current-state vocabulary
    (`comm_down`, `estopped`, `faulted`, `running`, `stopped`). Conditions are
    slugs of the bridge's own ERROR_CODES vocabulary, plus e_stop_active, so
    the consumer never has to parse prose.
    """
    conditions: List[str] = []
    code = int(snapshot.error_code)

    if bool(snapshot.e_stop):
        conditions.append("e_stop_active")

    if code == COMM_LOSS_ERROR_CODE:
        conditions.append(_slug(ERROR_CODES[COMM_LOSS_ERROR_CODE]))
        return "comm_down", conditions

    if bool(snapshot.e_stop):
        return "estopped", conditions

    if bool(snapshot.fault_alarm) or code != 0:
        if code != 0:
            conditions.append(_slug(ERROR_CODES.get(code, "unknown error %d" % code)))
        else:
            conditions.append("fault_alarm")
        return "faulted", conditions

    if bool(snapshot.motor_running or snapshot.conveyor_running):
        return "running", conditions

    return "stopped", conditions


def _tag_quality(tag_path: str, comm_ok: bool, unsourced: frozenset) -> str:
    """Per-tag quality under the downgrade-only rule.

    A tag whose backing signal was never read (`unsourced` — e.g.
    height_sensor_mm / sort_divert_active on a bench map with no such I/O) is
    `uncertain` even with healthy comms: its value is a deterministic default,
    not an observation, and claiming `good` would invent plant data. With
    comms lost, the measurement values are whatever the bridge last held —
    `uncertain`, never `good`. `comm_ok` and `fault_code` stay `good` because
    they ARE the bridge's own directly-known state (error code 5 is produced by
    the bridge, not read across the dead link).
    """
    if tag_path in unsourced:
        return "uncertain"
    if comm_ok:
        return "good"
    if tag_path in ("conv_simple.comm_ok", "conv_simple.fault_code"):
        return "good"
    return "uncertain"


def build_machine_snapshot_envelope(
    snapshot: TagSnapshot,
    *,
    tenant_id: str,
    snapshot_id: str,
    gateway_id: str,
    source_record_id: str,
    proposed_uns_path: str,
    source_snapshot_ref: str = "",
) -> Dict[str, Any]:
    """Build a `factorylm.machine-snapshot.v1` envelope from one TagSnapshot.

    Deterministic: the same snapshot and identifiers produce an identical
    envelope (no clocks, no randomness — `snapshot_id` is caller-supplied
    per the contract's "uuid-or-stable-source-id").
    """
    if not tenant_id:
        raise ValueError(
            "tenant_id is required — the contract forbids defaulting or "
            "inferring it (PRD 'Contract rules')"
        )
    if not snapshot_id:
        raise ValueError("snapshot_id is required")
    captured_at = snapshot.timestamp
    if not captured_at:
        raise ValueError(
            "snapshot has no timestamp — captured_at must come from the "
            "source; inventing freshness is forbidden"
        )

    canonical = canonical_tags_from_snapshot(snapshot)
    comm_ok = bool(canonical["conv_simple.comm_ok"])
    unsourced = unsourced_canonical_tags(snapshot)

    tags = [
        {
            "tag_path": tag_path,
            "value": value,
            "quality": _tag_quality(tag_path, comm_ok, unsourced),
            "observed_at": captured_at,
        }
        for tag_path, value in sorted(canonical.items())
    ]

    state, conditions = machine_state_from_snapshot(snapshot)

    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "source_system": SOURCE_SYSTEM,
        "captured_at": captured_at,
        "tenant_id": tenant_id,
        "asset": {
            "source_record_id": source_record_id,
            "proposed_uns_path": proposed_uns_path,
        },
        "machine_state": state,
        "active_conditions": conditions,
        "tags": tags,
        "provenance": {
            "producer": PRODUCER,
            "gateway_id": gateway_id,
            "source_snapshot_ref": source_snapshot_ref or snapshot.node_id,
        },
    }


def validate_envelope(envelope: Any) -> List[str]:
    """Contract-rule check. Returns a list of violations; empty means valid.

    This is the producer's self-check and the test harness for the shared
    fixtures — the four invalid fixtures must each fail here for their
    documented reason, and the valid fixture must pass untouched.
    """
    violations: List[str] = []
    if not isinstance(envelope, dict):
        return ["envelope is not an object"]

    if envelope.get("schema_version") != SCHEMA_VERSION:
        violations.append(
            "schema_version must be %r, got %r"
            % (SCHEMA_VERSION, envelope.get("schema_version"))
        )
    if envelope.get("source_system") != SOURCE_SYSTEM:
        violations.append(
            "source_system must be %r, got %r"
            % (SOURCE_SYSTEM, envelope.get("source_system"))
        )
    for required in ("snapshot_id", "captured_at", "tenant_id"):
        if not envelope.get(required):
            violations.append("missing required field: %s" % required)

    tags = envelope.get("tags")
    if not isinstance(tags, list) or not tags:
        violations.append("tags must be a non-empty list")
        tags = []

    for i, tag in enumerate(tags):
        if not isinstance(tag, dict):
            violations.append("tags[%d] is not an object" % i)
            continue
        path = tag.get("tag_path")
        if not path or not isinstance(path, str):
            violations.append("tags[%d] missing tag_path" % i)
        elif re.fullmatch(r"(register|reg|hr|coil)[_ ]?\d+", path.strip().lower()):
            violations.append(
                "tags[%d] tag_path %r is a raw register reference — canonical "
                "names only" % (i, path)
            )
        elif path not in REQUIRED_CANONICAL_TAGS:
            violations.append(
                "tags[%d] tag_path %r is not in the canonical FactoryLM tag "
                "set" % (i, path)
            )
        if "value" not in tag:
            violations.append("tags[%d] missing value" % i)
        # Unknown/missing quality is NOT a violation: per the PRD, the
        # consumer downgrades it toward less confidence (`uncertain`), never
        # to `good` — so the validator accepts it rather than rejecting,
        # mirroring the MIRA adapter's consumption semantics.
        if not tag.get("observed_at"):
            violations.append("tags[%d] missing observed_at" % i)

    def _walk(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for key, val in obj.items():
                lowered = str(key).lower()
                if any(tok in lowered for tok in FORBIDDEN_FIELD_TOKENS):
                    violations.append(
                        "forbidden command/write field %r at %s — the payload "
                        "is observation-only" % (key, path)
                    )
                _walk(val, "%s.%s" % (path, key))
        elif isinstance(obj, list):
            for j, item in enumerate(obj):
                _walk(item, "%s[%d]" % (path, j))

    _walk(envelope, "$")
    return violations
