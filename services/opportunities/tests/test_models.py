"""Tests for opportunity models."""

import pytest
from datetime import datetime, timedelta

from ..models import (
    Opportunity,
    OpportunityType,
    OpportunityStatus,
    RAGStatus,
)


class TestOpportunity:
    """Tests for Opportunity dataclass."""

    def test_create_opportunity(self):
        """Test creating a basic opportunity."""
        opp = Opportunity(
            name="Test Conference 2026",
            organizer="Test Org",
            type=OpportunityType.CONFERENCE,
            url="https://example.com",
        )

        assert opp.name == "Test Conference 2026"
        assert opp.organizer == "Test Org"
        assert opp.type == OpportunityType.CONFERENCE
        assert opp.status == OpportunityStatus.DISCOVERED
        assert opp.progress_percent == 0
        assert opp.rag_status == RAGStatus.GREY

    def test_primary_deadline_conference(self):
        """Test primary deadline for conference is CFP deadline."""
        opp = Opportunity(
            name="Test Conference",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime(2026, 3, 15),
            registration_deadline=datetime(2026, 4, 1),
        )

        assert opp.get_primary_deadline() == datetime(2026, 3, 15)

    def test_primary_deadline_accelerator(self):
        """Test primary deadline for accelerator is application deadline."""
        opp = Opportunity(
            name="Test Accelerator",
            type=OpportunityType.ACCELERATOR,
            application_deadline=datetime(2026, 4, 1),
        )

        assert opp.get_primary_deadline() == datetime(2026, 4, 1)

    def test_days_until_deadline(self):
        """Test days calculation."""
        future = datetime.utcnow() + timedelta(days=10)
        opp = Opportunity(
            name="Test",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=future,
        )

        days = opp.days_until_deadline()
        assert days is not None
        assert 9 <= days <= 10  # Allow for timing edge cases

    def test_days_until_deadline_no_deadline(self):
        """Test days calculation with no deadline."""
        opp = Opportunity(name="Test", type=OpportunityType.CONFERENCE)
        assert opp.days_until_deadline() is None

    def test_rag_status_green(self):
        """Test GREEN status: >50% complete with >14 days remaining."""
        opp = Opportunity(
            name="Test",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime.utcnow() + timedelta(days=30),
            progress_percent=60,
        )

        assert opp.calculate_rag_status() == RAGStatus.GREEN

    def test_rag_status_yellow_low_progress(self):
        """Test YELLOW status: <50% complete."""
        opp = Opportunity(
            name="Test",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime.utcnow() + timedelta(days=30),
            progress_percent=40,
        )

        assert opp.calculate_rag_status() == RAGStatus.YELLOW

    def test_rag_status_yellow_low_time(self):
        """Test YELLOW status: <14 days remaining."""
        opp = Opportunity(
            name="Test",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime.utcnow() + timedelta(days=10),
            progress_percent=60,
        )

        assert opp.calculate_rag_status() == RAGStatus.YELLOW

    def test_rag_status_red_very_low_progress(self):
        """Test RED status: <25% complete."""
        opp = Opportunity(
            name="Test",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime.utcnow() + timedelta(days=30),
            progress_percent=20,
        )

        assert opp.calculate_rag_status() == RAGStatus.RED

    def test_rag_status_red_very_low_time(self):
        """Test RED status: <7 days remaining."""
        opp = Opportunity(
            name="Test",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime.utcnow() + timedelta(days=5),
            progress_percent=60,
        )

        assert opp.calculate_rag_status() == RAGStatus.RED

    def test_rag_status_grey_no_deadline(self):
        """Test GREY status: no deadline."""
        opp = Opportunity(name="Test", type=OpportunityType.CONFERENCE)

        assert opp.calculate_rag_status() == RAGStatus.GREY

    def test_to_dict_from_dict_roundtrip(self):
        """Test serialization roundtrip."""
        opp = Opportunity(
            name="Test Conference",
            organizer="Test Org",
            type=OpportunityType.CONFERENCE,
            url="https://example.com",
            cfp_deadline=datetime(2026, 3, 15, 12, 0, 0),
            event_start=datetime(2026, 5, 1),
            event_end=datetime(2026, 5, 3),
            location="San Jose, CA",
            progress_percent=50,
            materials_checklist={"paper": True, "video": False},
            tags=["ai", "ml"],
        )

        data = opp.to_dict()
        restored = Opportunity.from_dict(data)

        assert restored.name == opp.name
        assert restored.organizer == opp.organizer
        assert restored.type == opp.type
        assert restored.cfp_deadline == opp.cfp_deadline
        assert restored.progress_percent == opp.progress_percent
        assert restored.materials_checklist == opp.materials_checklist
        assert restored.tags == opp.tags

    def test_update_rag_status(self):
        """Test automatic RAG status update."""
        opp = Opportunity(
            name="Test",
            type=OpportunityType.CONFERENCE,
            cfp_deadline=datetime.utcnow() + timedelta(days=30),
            progress_percent=60,
            rag_status=RAGStatus.GREY,  # Initial wrong status
        )

        opp.update_rag_status()

        assert opp.rag_status == RAGStatus.GREEN
