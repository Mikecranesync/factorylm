"""
FMSys Workshop adapter.
https://fmsys-org.github.io/2026/
"""

import logging
import re
from datetime import datetime
from typing import List

from ..models import Opportunity, OpportunityType, OpportunityStatus
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class FMSysAdapter(BaseAdapter):
    """Adapter for FMSys Workshop (Foundation Models for Systems)."""

    name = "fmsys"
    source_url = "https://fmsys-org.github.io/2026/"

    KNOWN_DATA = {
        "name": "FMSys 2026 Workshop",
        "organizer": "FMSys Organization",
        "url": "https://fmsys-org.github.io/2026/",
        "type": OpportunityType.WORKSHOP,
        "location": "Co-located with MLSys 2026",
        "timezone": "America/Los_Angeles",
    }

    def fetch(self) -> List[Opportunity]:
        """Fetch FMSys 2026 opportunities."""
        opportunities = []

        try:
            html = self.fetch_html(self.source_url)
            opp = self._parse_page(html)
            if opp:
                opportunities.append(opp)
        except Exception as e:
            logger.warning(f"Could not fetch FMSys page: {e}")
            opp = self._create_from_known_data()
            opportunities.append(opp)

        return opportunities

    def _parse_page(self, html: str) -> Opportunity:
        """Parse the main page for dates."""
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
                "paper_draft": False,
                "extended_abstract": False,
            },
        )

        # Try to extract paper submission deadline
        deadline_patterns = [
            r"paper\s+(?:submission\s+)?deadline[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})",
            r"submission\s+deadline[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})",
            r"([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})\s*[-–]\s*paper",
        ]

        for pattern in deadline_patterns:
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
                    try:
                        parsed_date = datetime.strptime(date_str, "%b %d, %Y")
                        if opp.cfp_deadline is None:
                            opp.cfp_deadline = parsed_date
                            break
                    except ValueError:
                        continue

        # Extract workshop date
        workshop_pattern = r"workshop[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})"
        workshop_match = re.search(workshop_pattern, html, re.IGNORECASE)
        if workshop_match:
            try:
                month_str, day, year = workshop_match.groups()
                opp.event_start = datetime.strptime(f"{month_str} {day}, {year}", "%B %d, %Y")
                opp.event_end = opp.event_start  # Single day workshop
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
                "extended_abstract": False,
            },
        )
