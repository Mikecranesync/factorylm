"""The cross-repo fixture boundary is enforced on THIS side too (#208).

`contracts/machine_snapshot/` is vendored **verbatim in two repositories** —
FactoryLM (producer, `machine_snapshot.build_machine_snapshot_envelope`) and
MIRA (consumer, `overlay_from_factorylm_snapshot`). MIRA PRD #3048 calls it
"the compatibility boundary between repositories; both projects must test
against the exact same payload."

A checksum guard on ONE side does not protect the boundary: the failure mode is
a *one-sided edit*, and the repo that edits its own copy keeps passing against
it. Both sides must assert the same manifest, so an edit here goes red here and
an edit in MIRA goes red there.

`CHECKSUMS.sha256` is vendored byte-identical from MIRA (`materialized_evidence/
tests/test_machine_snapshot_fixture_integrity.py` is the mirror of this file).
Regenerate deliberately, in BOTH repos, in the same change:

    cd contracts/machine_snapshot && shasum -a 256 \\
      README.md snapshot_v1_valid.json snapshot_v1_invalid_malformed_tags.json \\
      snapshot_v1_invalid_missing_tenant.json \\
      snapshot_v1_invalid_missing_timestamp.json \\
      snapshot_v1_invalid_schema_version.json \\
      | awk '{printf "%s  %s\\n", $1, $2}' > CHECKSUMS.sha256
"""

import hashlib
import os

import pytest

FIXTURES = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "contracts", "machine_snapshot")
)
MANIFEST = os.path.join(FIXTURES, "CHECKSUMS.sha256")


def _manifest_rows():
    rows = []
    with open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            digest, _, name = line.partition("  ")
            rows.append((name, digest))
    return rows


def test_manifest_exists_and_is_not_empty():
    assert os.path.isfile(MANIFEST), f"missing {MANIFEST}"
    assert _manifest_rows(), "CHECKSUMS.sha256 lists no files — the guard would pass vacuously"


@pytest.mark.parametrize("name,expected", _manifest_rows())
def test_fixture_matches_its_recorded_checksum(name, expected):
    path = os.path.join(FIXTURES, name)
    assert os.path.isfile(path), f"{name} is in CHECKSUMS.sha256 but missing from the tree"
    with open(path, "rb") as fh:
        actual = hashlib.sha256(fh.read()).hexdigest()
    assert actual == expected, (
        f"{name} changed without updating CHECKSUMS.sha256.\n"
        "This file is vendored verbatim in BOTH repos — update it in FactoryLM and "
        "MIRA together and regenerate the manifest in both, or the producer and "
        "consumer silently stop testing the same payload."
    )


def test_every_fixture_on_disk_is_covered_by_the_manifest():
    """A new fixture must be listed, or it is unguarded.

    Without this, someone adds `snapshot_v1_invalid_whatever.json`, every
    per-file check still passes, and the new file drifts freely — the guard
    looks green while covering less than it claims.
    """
    on_disk = {
        f
        for f in os.listdir(FIXTURES)
        if os.path.isfile(os.path.join(FIXTURES, f)) and f != os.path.basename(MANIFEST)
    }
    listed = {name for name, _ in _manifest_rows()}
    assert on_disk == listed, (
        f"unguarded fixture files: {sorted(on_disk - listed)}; "
        f"listed but absent: {sorted(listed - on_disk)}"
    )
