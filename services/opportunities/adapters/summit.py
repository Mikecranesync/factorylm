"""
AI in Manufacturing Summit adapter.
https://sites.psu.edu/aims/
"""

import logging
import re
from datetime import datetime
from typing import List

from ..models import Opportunity, OpportunityType, OpportunityStatus
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class AIMfgSummitAdapter(BaseAdapter):
    """Adapter for AI in Manufacturing Summit (Penn State)."""

    name = "aims"
    source_url = "https://sites.psu.edu/aims/"

    KNOWN_DATA = {
        "name": "AI in Manufacturing Summit 2026",
        "organizer": "Penn State University",
        "url": "https://sites.psu.edu/aims/",
        "type": OpportunityType.SUMMIT,
        "location": "Penn State, PA",
        "timezone": "America/New_York",
    }

    def fetch(self) -> List[Opportunity]:
        """Fetch AI Manufacturing Summit opportunities."""
        opportunities = []

        try:
            html = self.fetch_html(self.source_url)
            opp = self._parse_page(html)
            if opp:
                opportunities.append(opp)
        except Exception as e:
            logger.warning(f"Could not fetch AIMS page: {e}")
            opp = self._create_from_known_data()
            opportunities.append(opp)

        return opportunities

    def _parse_page(self, html: str) -> Opportunity:
        """Parse the summit page for dates."""
        opp = Opportunity(
            name=self.KNOWN_DATA["name"],
            organizer=self.KNOWN_DATA["organizer"],
            url=self.KNOWN_DATA["url"],
            type=self.KNOWN_DATA["type"],
            location=self.KNOWN_DATA["location"],
            timezone=self.KNOWN_DATA["timezone"],
            source=self.name,
            source_url=self.source_url,
            status=OpportunityStatus.PARSED,
            materials_checklist={
                "registration": False,
                "poster_abstract": False,
                "travel_booked": False,
            },
        )

        # Try to extract registration deadline
        reg_patterns = [
            r"registration\s+(?:deadline)?[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})",
            r"register\s+by[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})",
        ]

        for pattern in reg_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                try:
                    month_str, day, year = match
                    date_str = f"{month_str} {day}, {year}"
                    parsed_date = datetime.strptime(date_str, "%B %d, %Y")
                    if opp.registration_deadline is None:
                        opp.registration_deadline = parsed_date
                        break
                except ValueError:
                    continue

        # Extract summit dates
        summit_patterns = [
            r"summit[:\s]*([A-Za-z]+)\s+(\d{1,2})[-–](\d{1,2}),?\s*(\d{4})",
            r"([A-Za-z]+)\s+(\d{1,2})[-–](\d{1,2}),?\s*(\d{4})\s*summit",
            r"date[:\s]*([A-Za-z]+)\s+(\d{1,2})[-–](\d{1,2}),?\s*(\d{4})",
        ]

        for pattern in summit_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    month_str, start_day, end_day, year = match.groups()
                    opp.event_start = datetime.strptime(f"{month_str} {start_day}, {year}", "%B %d, %Y")
                    opp.event_end = datetime.strptime(f"{month_str} {end_day}, {year}", "%B %d, %Y")
                    break
                except ValueError:
                    continue

        return opp

    def _create_from_known_data(self) -> Opportunity:
        """Create opportunity from known/estimated data."""
        return Opportunity(
            name=self.KNOWN_DATA["name"],
            organizer=self.KNOWN_DATA["organizer"],
            url=self.KNOWN_DATA["url"],
            type=self.KNOWN_DATA["type"],
            location=self.KNOWN_DATA["location"],
            timezone=self.KNOWN_DATA["timezone"],
            source=self.name,
            source_url=self.source_url,
            status=OpportunityStatus.DISCOVERED,
            notes="Dates pending - check website for official dates",
            materials_checklist={
                "registration": False,
                "poster_abstract": False,
                "travel_booked": False,
            },
        )
