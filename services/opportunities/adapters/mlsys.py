"""
MLSys Conference adapter.
https://mlsys.org/Conferences/2026
"""

import logging
import re
from datetime import datetime
from typing import List

from ..models import Opportunity, OpportunityType, OpportunityStatus
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class MLSysAdapter(BaseAdapter):
    """Adapter for MLSys Conference (Machine Learning and Systems)."""

    name = "mlsys"
    source_url = "https://mlsys.org/Conferences/2026"

    # Known dates for MLSys 2026 (these would ideally be scraped)
    KNOWN_DATA = {
        "name": "MLSys 2026",
        "organizer": "MLSys Foundation",
        "url": "https://mlsys.org/Conferences/2026",
        "type": OpportunityType.CONFERENCE,
        "location": "San Jose, CA",  # Typical location
        "timezone": "America/Los_Angeles",
        # Dates are estimates based on historical patterns
        # MLSys typically: CFP in Sept, conference in May
    }

    def fetch(self) -> List[Opportunity]:
        """Fetch MLSys 2026 opportunities."""
        opportunities = []

        try:
            # Try to fetch and parse actual dates from the website
            html = self.fetch_html(f"{self.source_url}/CallForPapers")
            opp = self._parse_cfp_page(html)
            if opp:
                opportunities.append(opp)
        except Exception as e:
            logger.warning(f"Could not fetch MLSys CFP page: {e}")
            # Fall back to known/estimated data
            opp = self._create_from_known_data()
            opportunities.append(opp)

        return opportunities

    def _parse_cfp_page(self, html: str) -> Opportunity:
        """Parse the Call for Papers page for dates."""
        opp = Opportunity(
            name=self.KNOWN_DATA["name"],
            organizer=self.KNOWN_DATA["organizer"],
            url=self.KNOWN_DATA["url"],
            type=self.KNOWN_DATA["type"],
            location=self.KNOWN_DATA["location"],
            timezone=self.KNOWN_DATA["timezone"],
            source=self.name,
            source_url=f"{self.source_url}/CallForPapers",
            status=OpportunityStatus.PARSED,
            materials_checklist={
                "paper_draft": False,
                "supplementary": False,
                "camera_ready": False,
            },
        )

        # Try to extract dates from HTML
        # Pattern: "September 15, 2026" or "Sep 15, 2026"
        date_patterns = [
            r"(?:submission|deadline)[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})",
            r"([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})\s*(?:deadline|submission)",
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                try:
                    month_str, day, year = match
                    date_str = f"{month_str} {day}, {year}"
                    parsed_date = datetime.strptime(date_str, "%B %d, %Y")
                    if opp.cfp_deadline is None:
                        opp.cfp_deadline = parsed_date
                        break
                except ValueError:
                    continue

        # Extract conference dates
        conf_pattern = r"conference[:\s]*([A-Za-z]+)\s+(\d{1,2})[-–](\d{1,2}),?\s*(\d{4})"
        conf_match = re.search(conf_pattern, html, re.IGNORECASE)
        if conf_match:
            try:
                month_str, start_day, end_day, year = conf_match.groups()
                opp.event_start = datetime.strptime(f"{month_str} {start_day}, {year}", "%B %d, %Y")
                opp.event_end = datetime.strptime(f"{month_str} {end_day}, {year}", "%B %d, %Y")
            except ValueError:
                pass

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
                "paper_draft": False,
                "supplementary": False,
                "camera_ready": False,
            },
        )
