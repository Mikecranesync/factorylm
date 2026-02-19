"""
Robotics and Manufacturing Accelerators adapter.
Aggregates multiple accelerator programs.
"""

import logging
from datetime import datetime
from typing import List

from ..models import Opportunity, OpportunityType, OpportunityStatus
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class AcceleratorsAdapter(BaseAdapter):
    """Adapter for robotics/manufacturing accelerator programs."""

    name = "accelerators"
    source_url = "https://massrobotics.org"

    # Curated list of relevant accelerators
    ACCELERATORS = [
        {
            "name": "MassRobotics Accelerator 2026",
            "organizer": "MassRobotics",
            "url": "https://www.massrobotics.org/accelerator/",
            "type": OpportunityType.ACCELERATOR,
            "location": "Boston, MA",
            "timezone": "America/New_York",
            "notes": "6-month program for robotics startups",
            "materials": {
                "application_form": False,
                "pitch_deck": False,
                "demo_video": False,
                "team_bios": False,
            },
        },
        {
            "name": "AWS Industrial Innovation Fund",
            "organizer": "Amazon Web Services",
            "url": "https://aws.amazon.com/industrial/",
            "type": OpportunityType.ACCELERATOR,
            "location": "Virtual / Seattle, WA",
            "timezone": "America/Los_Angeles",
            "notes": "Funding and support for industrial AI/ML startups",
            "materials": {
                "application_form": False,
                "business_plan": False,
                "technical_overview": False,
            },
        },
        {
            "name": "Techstars Industries of the Future",
            "organizer": "Techstars",
            "url": "https://www.techstars.com/accelerators/industries-of-the-future",
            "type": OpportunityType.ACCELERATOR,
            "location": "Various",
            "timezone": "America/New_York",
            "notes": "Manufacturing, AI, robotics focus",
            "materials": {
                "application_form": False,
                "pitch_video": False,
                "financials": False,
            },
        },
        {
            "name": "NVIDIA Inception Program",
            "organizer": "NVIDIA",
            "url": "https://www.nvidia.com/en-us/startups/",
            "type": OpportunityType.INCUBATOR,
            "location": "Virtual",
            "timezone": "America/Los_Angeles",
            "notes": "GPU credits, technical support, networking for AI startups",
            "materials": {
                "application_form": False,
                "use_case_description": False,
            },
        },
        {
            "name": "HAX Hardware Accelerator",
            "organizer": "HAX / SOSV",
            "url": "https://hax.co/",
            "type": OpportunityType.ACCELERATOR,
            "location": "Shenzhen, China / Newark, NJ",
            "timezone": "America/New_York",
            "notes": "Hardware and robotics focus, $250K investment",
            "materials": {
                "application_form": False,
                "prototype_photos": False,
                "pitch_video": False,
                "team_info": False,
            },
        },
        {
            "name": "Manufacturing USA Innovation Grants",
            "organizer": "Manufacturing USA",
            "url": "https://www.manufacturingusa.com/",
            "type": OpportunityType.GRANT,
            "location": "National",
            "timezone": "America/New_York",
            "notes": "Federal grants for advanced manufacturing R&D",
            "materials": {
                "grant_proposal": False,
                "budget": False,
                "team_qualifications": False,
            },
        },
    ]

    def fetch(self) -> List[Opportunity]:
        """Fetch accelerator opportunities from curated list."""
        opportunities = []

        for accel in self.ACCELERATORS:
            opp = Opportunity(
                name=accel["name"],
                organizer=accel["organizer"],
                url=accel["url"],
                type=accel["type"],
                location=accel["location"],
                timezone=accel["timezone"],
                source=self.name,
                source_url=accel["url"],
                status=OpportunityStatus.DISCOVERED,
                notes=accel.get("notes", ""),
                materials_checklist=accel.get("materials", {}),
            )

            # Try to fetch actual dates from the website
            try:
                html = self.fetch_html(accel["url"])
                self._parse_dates(opp, html)
                opp.status = OpportunityStatus.PARSED
            except Exception as e:
                logger.debug(f"Could not fetch {accel['name']}: {e}")
                # Keep as DISCOVERED with no dates

            opportunities.append(opp)

        return opportunities

    def _parse_dates(self, opp: Opportunity, html: str) -> None:
        """Try to extract application deadline from HTML."""
        import re

        deadline_patterns = [
            r"application\s+(?:deadline)?[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})",
            r"apply\s+by[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})",
            r"deadline[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})",
        ]

        for pattern in deadline_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                try:
                    month_str, day, year = match
                    date_str = f"{month_str} {day}, {year}"
                    parsed_date = datetime.strptime(date_str, "%B %d, %Y")
                    if opp.application_deadline is None:
                        opp.application_deadline = parsed_date
                        return
                except ValueError:
                    continue

        # Check for program dates
        program_patterns = [
            r"program\s+(?:starts?|begins?)[:\s]*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})",
            r"cohort[:\s]*([A-Za-z]+)\s+(\d{4})",
        ]

        for pattern in program_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 3:
                        month_str, day, year = groups
                        opp.event_start = datetime.strptime(f"{month_str} {day}, {year}", "%B %d, %Y")
                    elif len(groups) == 2:
                        month_str, year = groups
                        opp.event_start = datetime.strptime(f"{month_str} 1, {year}", "%B %d, %Y")
                    break
                except ValueError:
                    continue
