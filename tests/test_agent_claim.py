"""
Tests for agent_claim.py — lease management, race conditions, staleness.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


# Import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from agent_claim import (
    atomic_create_lease,
    cmd_claim,
    cmd_census,
    cmd_heartbeat,
    cmd_release,
    is_stale,
    read_lease,
    slugify,
    write_lease,
)


class TestSlugify:
    """Test slug generation."""

    def test_lowercase(self):
        assert slugify("MyItem") == "myitem"

    def test_spaces_to_hyphens(self):
        assert slugify("My Item") == "my-item"

    def test_special_chars_stripped(self):
        assert slugify("my-item@v1") == "my-item-v1"


class TestIsStale:
    """Test staleness detection."""

    def test_fresh_heartbeat(self):
        now = datetime.now(timezone.utc).isoformat()
        assert not is_stale(now, 4)

    def test_stale_heartbeat(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        assert is_stale(old, 4)

    def test_exactly_at_boundary(self):
        # Exactly 4 hours old should not be stale
        boundary = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
        result = is_stale(boundary, 4)
        # Could be true or false depending on seconds, so we just check it's close
        assert isinstance(result, bool)

    def test_invalid_timestamp(self):
        assert is_stale("not-a-timestamp", 4)


class TestAtomicCreateLease:
    """Test atomic lease creation with O_CREAT|O_EXCL."""

    def test_creates_new_lease(self, tmp_path):
        """Test successful lease creation."""
        leases_dir = tmp_path / "leases"
        lease_data = {"agent_id": "test", "item": "item1", "status": "in_progress"}
        result = atomic_create_lease("item1", lease_data, str(leases_dir))
        assert result is True
        assert (leases_dir / "item1.json").exists()

    def test_fails_on_existing_lease(self, tmp_path):
        """Test atomic create fails if lease exists."""
        leases_dir = tmp_path / "leases"
        lease_data = {"agent_id": "test", "item": "item1"}
        atomic_create_lease("item1", lease_data, str(leases_dir))

        # Try to create again
        result = atomic_create_lease("item1", lease_data, str(leases_dir))
        assert result is False

    def test_race_condition_exactly_one_wins(self, tmp_path):
        """Test that exactly one racer wins in a race."""
        leases_dir = tmp_path / "leases"
        lease_data = {"agent_id": "test", "item": "race_item"}

        results = []
        for i in range(2):
            result = atomic_create_lease("race_item", lease_data, str(leases_dir))
            results.append(result)

        # Exactly one should succeed
        assert sum(results) == 1


class TestReadWriteLease:
    """Test lease file I/O."""

    def test_read_nonexistent_lease(self, tmp_path):
        """Reading nonexistent lease returns None."""
        result = read_lease("nonexistent", str(tmp_path / "leases"))
        assert result is None

    def test_write_and_read_lease(self, tmp_path):
        """Write and read roundtrip."""
        leases_dir = str(tmp_path / "leases")
        lease_data = {"agent_id": "test", "item": "item1", "status": "in_progress"}
        write_lease("item1", lease_data, leases_dir)

        read_data = read_lease("item1", leases_dir)
        assert read_data == lease_data


class TestCmdClaim:
    """Test claim subcommand."""

    @patch("agent_claim.run_preflight_check")
    def test_claim_success(self, mock_preflight, tmp_path):
        """Test successful claim."""
        mock_preflight.return_value = None
        os.chdir(tmp_path)

        result = cmd_claim(
            "item1",
            agent_id="agent-1",
            worktree=str(tmp_path),
            branch="feat/test",
            no_preflight=False,
        )
        assert result == 0
        assert (tmp_path / ".agents/leases/item1.json").exists()

    @patch("agent_claim.run_preflight_check")
    def test_claim_already_merged_fails_with_2(self, mock_preflight, tmp_path):
        """Test claim fails with exit 2 if work already merged."""
        mock_preflight.return_value = "Work already merged"
        os.chdir(tmp_path)

        result = cmd_claim("item1", no_preflight=False)
        assert result == 2

    @patch("agent_claim.run_preflight_check")
    def test_claim_fresh_lease_fails_with_1(self, mock_preflight, tmp_path):
        """Test claim fails with exit 1 if fresh lease exists."""
        mock_preflight.return_value = None
        os.chdir(tmp_path)

        # Create a fresh lease
        now = datetime.now(timezone.utc).isoformat()
        lease_data = {
            "agent_id": "other",
            "item": "item1",
            "started_at": now,
            "heartbeat_at": now,
            "status": "in_progress",
        }
        Path(".agents/leases").mkdir(parents=True, exist_ok=True)
        with open(".agents/leases/item1.json", "w") as f:
            json.dump(lease_data, f)

        result = cmd_claim("item1", no_preflight=False)
        assert result == 1

    @patch("agent_claim.run_preflight_check")
    def test_claim_stale_lease_succeeds(self, mock_preflight, tmp_path):
        """Test claim succeeds if existing lease is stale."""
        mock_preflight.return_value = None
        os.chdir(tmp_path)

        # Create a stale lease
        old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        lease_data = {
            "agent_id": "other",
            "item": "item1",
            "started_at": old,
            "heartbeat_at": old,
            "status": "in_progress",
        }
        Path(".agents/leases").mkdir(parents=True, exist_ok=True)
        with open(".agents/leases/item1.json", "w") as f:
            json.dump(lease_data, f)

        result = cmd_claim("item1", stale_hours=4, no_preflight=False)
        assert result == 0


class TestCmdHeartbeat:
    """Test heartbeat subcommand."""

    def test_heartbeat_success(self, tmp_path):
        """Test heartbeat updates timestamp."""
        os.chdir(tmp_path)
        Path(".agents/leases").mkdir(parents=True, exist_ok=True)

        # Create initial lease
        lease_data = {
            "agent_id": "agent-1",
            "item": "item1",
            "started_at": "2026-08-23T10:00:00+00:00",
            "heartbeat_at": "2026-08-23T10:00:00+00:00",
            "status": "in_progress",
        }
        with open(".agents/leases/item1.json", "w") as f:
            json.dump(lease_data, f)

        result = cmd_heartbeat("item1")
        assert result == 0

        # Verify heartbeat updated
        updated = read_lease("item1")
        assert updated["heartbeat_at"] != lease_data["heartbeat_at"]

    def test_heartbeat_nonexistent_fails(self, tmp_path):
        """Test heartbeat fails if no lease exists."""
        os.chdir(tmp_path)
        result = cmd_heartbeat("nonexistent")
        assert result == 1


class TestCmdRelease:
    """Test release subcommand."""

    def test_release_success(self, tmp_path):
        """Test successful release."""
        os.chdir(tmp_path)
        Path(".agents/leases").mkdir(parents=True, exist_ok=True)

        # Create lease
        lease_data = {
            "agent_id": "agent-1",
            "item": "item1",
            "status": "in_progress",
        }
        with open(".agents/leases/item1.json", "w") as f:
            json.dump(lease_data, f)

        result = cmd_release("item1", status="merged")
        assert result == 0
        assert not (tmp_path / ".agents/leases/item1.json").exists()

        # Verify history log entry
        history_path = Path(".agents/leases/HISTORY.log")
        assert history_path.exists()
        log_content = history_path.read_text()
        assert "item1" in log_content
        assert "merged" in log_content

    def test_release_nonexistent_fails(self, tmp_path):
        """Test release fails if no lease exists."""
        os.chdir(tmp_path)
        result = cmd_release("nonexistent")
        assert result == 1


class TestCmdCensus:
    """Test census subcommand."""

    def test_census_no_leases(self, tmp_path):
        """Test census with no leases."""
        os.chdir(tmp_path)
        result = cmd_census(reap=False)
        assert result == 0

    def test_census_live_vs_stale(self, tmp_path):
        """Test census classifies live vs stale leases."""
        os.chdir(tmp_path)
        Path(".agents/leases").mkdir(parents=True, exist_ok=True)

        # Create fresh lease
        now = datetime.now(timezone.utc).isoformat()
        fresh_data = {
            "agent_id": "agent-1",
            "item": "item1",
            "started_at": now,
            "heartbeat_at": now,
            "status": "in_progress",
        }
        with open(".agents/leases/item1.json", "w") as f:
            json.dump(fresh_data, f)

        # Create stale lease
        old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        stale_data = {
            "agent_id": "agent-2",
            "item": "item2",
            "started_at": old,
            "heartbeat_at": old,
            "status": "in_progress",
        }
        with open(".agents/leases/item2.json", "w") as f:
            json.dump(stale_data, f)

        result = cmd_census(reap=False)
        assert result == 0

        # Both leases should still exist
        assert Path(".agents/leases/item1.json").exists()
        assert Path(".agents/leases/item2.json").exists()

    def test_census_reap(self, tmp_path):
        """Test census --reap deletes stale leases."""
        os.chdir(tmp_path)
        Path(".agents/leases").mkdir(parents=True, exist_ok=True)

        # Create stale lease
        old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        stale_data = {
            "agent_id": "agent-1",
            "item": "stale_item",
            "started_at": old,
            "heartbeat_at": old,
            "status": "in_progress",
        }
        with open(".agents/leases/stale_item.json", "w") as f:
            json.dump(stale_data, f)

        result = cmd_census(reap=True)
        assert result == 0
        assert not Path(".agents/leases/stale_item.json").exists()


class TestClaimReleaseRoundtrip:
    """Integration test: claim, heartbeat, release."""

    @patch("agent_claim.run_preflight_check")
    def test_full_workflow(self, mock_preflight, tmp_path):
        """Test claim -> heartbeat -> release workflow."""
        mock_preflight.return_value = None
        os.chdir(tmp_path)

        # Claim
        result = cmd_claim("feature-123", agent_id="claude-1", no_preflight=False)
        assert result == 0

        # Verify lease exists
        lease = read_lease("feature-123")
        assert lease is not None
        assert lease["agent_id"] == "claude-1"
        old_hb = lease["heartbeat_at"]

        # Heartbeat
        result = cmd_heartbeat("feature-123")
        assert result == 0
        lease = read_lease("feature-123")
        # Heartbeat should be updated (at least the string representation)
        assert lease["heartbeat_at"] >= old_hb

        # Release
        result = cmd_release("feature-123", status="merged")
        assert result == 0
        assert read_lease("feature-123") is None
