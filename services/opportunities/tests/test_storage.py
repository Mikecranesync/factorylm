"""Tests for opportunities storage."""

import os
import pytest
import tempfile
from datetime import datetime, timedelta

from ..models import Opportunity, OpportunityType, OpportunityStatus, RAGStatus
from ..storage import OpportunitiesStorage


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Windows may hold file locks, so ignore cleanup errors
    try:
        os.unlink(path)
    except PermissionError:
        pass  # File will be cleaned up by OS temp cleanup


@pytest.fixture
def storage(temp_db):
    """Create storage instance with temp database."""
    return OpportunitiesStorage(temp_db)


class TestOpportunitiesStorage:
    """Tests for OpportunitiesStorage."""

    def test_create_and_get(self, storage):
        """Test creating and retrieving an opportunity."""
        opp = Opportunity(
            name="Test Conference",
            organizer="Test Org",
            type=OpportunityType.CONFERENCE,
            url="https://example.com",
        )

        created = storage.create(opp)
        retrieved = storage.get(created.id)

        assert retrieved is not None
        assert retrieved.name == "Test Conference"
        assert retrieved.organizer == "Test Org"

    def test_get_by_name(self, storage):
        """Test retrieving by name."""
        opp = Opportunity(
            name="MLSys 2026",
            type=OpportunityType.CONFERENCE,
        )
        storage.create(opp)

        retrieved = storage.get_by_name("MLSys 2026")

        assert retrieved is not None
        assert retrieved.name == "MLSys 2026"

    def test_update(self, storage):
        """Test updating an opportunity."""
        opp = Opportunity(
            name="Test",
            type=OpportunityType.CONFERENCE,
            progress_percent=0,
        )
        storage.create(opp)

        opp.progress_percent = 50
        opp.status = OpportunityStatus.TRACKING
        storage.update(opp)

        retrieved = storage.get(opp.id)
        assert retrieved.progress_percent == 50
        assert retrieved.status == OpportunityStatus.TRACKING

    def test_upsert_new(self, storage):
        """Test upsert creates new record."""
        opp = Opportunity(
            name="New Conference",
            type=OpportunityType.CONFERENCE,
            source="test",
        )

        result = storage.upsert(opp)

        assert storage.get(result.id) is not None

    def test_upsert_existing(self, storage):
        """Test upsert updates existing record."""
        opp1 = Opportunity(
            name="Existing Conference",
            type=OpportunityType.CONFERENCE,
            source="test",
            progress_percent=0,
        )
        storage.create(opp1)

        opp2 = Opportunity(
            name="Existing Conference",
            type=OpportunityType.CONFERENCE,
            source="test",
            progress_percent=50,
        )
        result = storage.upsert(opp2)

        # Should have same ID
        assert result.id == opp1.id
        # Should have updated progress
        retrieved = storage.get(opp1.id)
        assert retrieved.progress_percent == 50

    def test_delete(self, storage):
        """Test deleting an opportunity."""
        opp = Opportunity(name="To Delete", type=OpportunityType.CONFERENCE)
        storage.create(opp)

        assert storage.delete(opp.id) is True
        assert storage.get(opp.id) is None

    def test_list_all(self, storage):
        """Test listing all opportunities."""
        for i in range(3):
            storage.create(Opportunity(
                name=f"Conference {i}",
                type=OpportunityType.CONFERENCE,
            ))

        all_opps = storage.list_all()
        assert len(all_opps) == 3

    def test_list_by_status(self, storage):
        """Test listing by status."""
        storage.create(Opportunity(
            name="Discovered",
            type=OpportunityType.CONFERENCE,
            status=OpportunityStatus.DISCOVERED,
        ))
        storage.create(Opportunity(
            name="Synced",
            type=OpportunityType.CONFERENCE,
            status=OpportunityStatus.SYNCED,
        ))

        discovered = storage.list_by_status(OpportunityStatus.DISCOVERED)
        assert len(discovered) == 1
        assert discovered[0].name == "Discovered"

    def test_list_by_source(self, storage):
        """Test listing by source."""
        storage.create(Opportunity(
            name="MLSys Test",
            type=OpportunityType.CONFERENCE,
            source="mlsys",
        ))
        storage.create(Opportunity(
            name="Other Test",
            type=OpportunityType.CONFERENCE,
            source="other",
        ))

        mlsys = storage.list_by_source("mlsys")
        assert len(mlsys) == 1
        assert mlsys[0].name == "MLSys Test"

    def test_list_upcoming(self, storage):
        """Test listing upcoming opportunities."""
        # Future deadline
        storage.create(Opportunity(
            name="Future",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime.utcnow() + timedelta(days=10),
        ))
        # Past deadline
        storage.create(Opportunity(
            name="Past",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime.utcnow() - timedelta(days=10),
        ))

        upcoming = storage.list_upcoming(days=30)

        # Should only include future deadline
        assert len(upcoming) == 1
        assert upcoming[0].name == "Future"

    def test_list_by_rag_status(self, storage):
        """Test listing by RAG status."""
        storage.create(Opportunity(
            name="Red Alert",
            type=OpportunityType.CONFERENCE,
            rag_status=RAGStatus.RED,
        ))
        storage.create(Opportunity(
            name="Green Light",
            type=OpportunityType.CONFERENCE,
            rag_status=RAGStatus.GREEN,
        ))

        red = storage.list_by_rag_status(RAGStatus.RED)
        assert len(red) == 1
        assert red[0].name == "Red Alert"

    def test_list_active(self, storage):
        """Test listing active (non-expired) opportunities."""
        storage.create(Opportunity(
            name="Active",
            type=OpportunityType.CONFERENCE,
            status=OpportunityStatus.TRACKING,
        ))
        storage.create(Opportunity(
            name="Expired",
            type=OpportunityType.CONFERENCE,
            status=OpportunityStatus.EXPIRED,
        ))

        active = storage.list_active()
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_update_all_rag_statuses(self, storage):
        """Test bulk RAG status update."""
        opp = Opportunity(
            name="Test",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime.utcnow() + timedelta(days=30),
            progress_percent=60,
            rag_status=RAGStatus.GREY,  # Wrong initial status
        )
        storage.create(opp)

        updated = storage.update_all_rag_statuses()

        assert updated == 1
        retrieved = storage.get(opp.id)
        assert retrieved.rag_status == RAGStatus.GREEN

    def test_count(self, storage):
        """Test count statistics."""
        storage.create(Opportunity(
            name="Test 1",
            type=OpportunityType.CONFERENCE,
            status=OpportunityStatus.DISCOVERED,
            rag_status=RAGStatus.GREEN,
        ))
        storage.create(Opportunity(
            name="Test 2",
            type=OpportunityType.ACCELERATOR,
            status=OpportunityStatus.SYNCED,
            rag_status=RAGStatus.RED,
        ))

        stats = storage.count()

        assert stats["total"] == 2
        assert stats["by_status"]["discovered"] == 1
        assert stats["by_status"]["synced"] == 1
        assert stats["by_rag"]["green"] == 1
        assert stats["by_rag"]["red"] == 1
