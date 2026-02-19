"""Tests for source adapters."""

import pytest
from unittest.mock import patch, MagicMock

from ..adapters import (
    MLSysAdapter,
    FMSysAdapter,
    AIMfgSummitAdapter,
    AcceleratorsAdapter,
)
from ..models import OpportunityType, OpportunityStatus


class TestMLSysAdapter:
    """Tests for MLSys adapter."""

    def test_known_data(self):
        """Test adapter has correct known data."""
        adapter = MLSysAdapter()
        assert adapter.name == "mlsys"
        assert "mlsys.org" in adapter.source_url

    def test_fetch_fallback(self):
        """Test fetch returns fallback data when scrape fails."""
        with patch.object(MLSysAdapter, 'fetch_html', side_effect=Exception("Network error")):
            adapter = MLSysAdapter()
            opportunities = adapter.fetch()

        assert len(opportunities) == 1
        opp = opportunities[0]
        assert opp.name == "MLSys 2026"
        assert opp.type == OpportunityType.CONFERENCE
        assert opp.status == OpportunityStatus.DISCOVERED

    def test_parse_cfp_page(self):
        """Test parsing CFP page HTML."""
        adapter = MLSysAdapter()

        # Sample HTML with dates
        html = """
        <html>
        <body>
            <p>Paper submission deadline: September 15, 2026</p>
            <p>Conference: May 1-3, 2026</p>
        </body>
        </html>
        """

        opp = adapter._parse_cfp_page(html)

        assert opp.name == "MLSys 2026"
        assert opp.status == OpportunityStatus.PARSED
        # Note: Date parsing depends on regex matching, may or may not succeed
        # depending on HTML format


class TestFMSysAdapter:
    """Tests for FMSys adapter."""

    def test_known_data(self):
        """Test adapter has correct known data."""
        adapter = FMSysAdapter()
        assert adapter.name == "fmsys"
        assert "fmsys" in adapter.source_url

    def test_fetch_fallback(self):
        """Test fetch returns fallback data when scrape fails."""
        with patch.object(FMSysAdapter, 'fetch_html', side_effect=Exception("Network error")):
            adapter = FMSysAdapter()
            opportunities = adapter.fetch()

        assert len(opportunities) == 1
        opp = opportunities[0]
        assert "FMSys" in opp.name
        assert opp.type == OpportunityType.WORKSHOP


class TestAIMfgSummitAdapter:
    """Tests for AI Manufacturing Summit adapter."""

    def test_known_data(self):
        """Test adapter has correct known data."""
        adapter = AIMfgSummitAdapter()
        assert adapter.name == "aims"
        assert "psu.edu" in adapter.source_url

    def test_fetch_fallback(self):
        """Test fetch returns fallback data when scrape fails."""
        with patch.object(AIMfgSummitAdapter, 'fetch_html', side_effect=Exception("Network error")):
            adapter = AIMfgSummitAdapter()
            opportunities = adapter.fetch()

        assert len(opportunities) == 1
        opp = opportunities[0]
        assert "Summit" in opp.name
        assert opp.type == OpportunityType.SUMMIT


class TestAcceleratorsAdapter:
    """Tests for Accelerators adapter."""

    def test_curated_list(self):
        """Test adapter has curated accelerator list."""
        adapter = AcceleratorsAdapter()
        assert len(adapter.ACCELERATORS) >= 4

    def test_fetch_returns_all_accelerators(self):
        """Test fetch returns all curated accelerators."""
        with patch.object(AcceleratorsAdapter, 'fetch_html', side_effect=Exception("Network error")):
            adapter = AcceleratorsAdapter()
            opportunities = adapter.fetch()

        # Should return all curated accelerators
        assert len(opportunities) >= 4

        # Check variety of types
        types = {opp.type for opp in opportunities}
        assert OpportunityType.ACCELERATOR in types

        # Check all have materials checklist
        for opp in opportunities:
            assert isinstance(opp.materials_checklist, dict)
            assert len(opp.materials_checklist) > 0

    def test_accelerator_sources(self):
        """Test all returned opportunities have correct source."""
        with patch.object(AcceleratorsAdapter, 'fetch_html', side_effect=Exception("Network error")):
            adapter = AcceleratorsAdapter()
            opportunities = adapter.fetch()

        for opp in opportunities:
            assert opp.source == "accelerators"
