"""
Google Calendar integration for syncing opportunity deadlines.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from .models import Opportunity, OpportunityType

logger = logging.getLogger(__name__)

# Google Calendar API imports (optional dependency)
try:
    from google.oauth2.credentials import Credentials
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAS_GOOGLE_API = True
except ImportError:
    HAS_GOOGLE_API = False
    logger.warning("Google Calendar API not installed. Run: pip install google-auth-oauthlib google-api-python-client")


SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarSync:
    """Sync opportunities to Google Calendar."""

    def __init__(
        self,
        calendar_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        service_account_path: Optional[str] = None,
        token_path: Optional[str] = None,
    ):
        self.calendar_id = calendar_id or os.environ.get(
            "GOOGLE_CALENDAR_ID", "primary"
        )
        self.credentials_path = credentials_path or os.environ.get(
            "GOOGLE_CREDENTIALS_PATH",
            os.path.expanduser("~/.config/google/credentials.json")
        )
        self.service_account_path = service_account_path or os.environ.get(
            "GOOGLE_SERVICE_ACCOUNT_KEY"
        )
        self.token_path = token_path or os.environ.get(
            "GOOGLE_TOKEN_PATH",
            os.path.expanduser("~/.config/google/token.json")
        )
        self._service = None

    def _get_credentials(self):
        """Get Google API credentials."""
        if not HAS_GOOGLE_API:
            raise RuntimeError("Google Calendar API not installed")

        creds = None

        # Try service account first
        if self.service_account_path and os.path.exists(self.service_account_path):
            creds = ServiceAccountCredentials.from_service_account_file(
                self.service_account_path, scopes=SCOPES
            )
            return creds

        # Try OAuth token
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Google credentials not found at {self.credentials_path}. "
                        "Download from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token for next run
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        return creds

    def _get_service(self):
        """Get Google Calendar API service."""
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def create_deadline_event(
        self,
        opp: Opportunity,
        deadline: datetime,
        deadline_type: str = "Deadline",
    ) -> dict:
        """Create a calendar event for a deadline."""
        service = self._get_service()

        event = {
            "summary": f"[{deadline_type}] {opp.name}",
            "description": self._build_description(opp, deadline_type),
            "start": {
                "date": deadline.strftime("%Y-%m-%d"),
                "timeZone": opp.timezone,
            },
            "end": {
                "date": deadline.strftime("%Y-%m-%d"),
                "timeZone": opp.timezone,
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60 * 24 * 7},  # 1 week
                    {"method": "popup", "minutes": 60 * 24 * 3},  # 3 days
                    {"method": "popup", "minutes": 60 * 24},      # 1 day
                ],
            },
            "colorId": self._get_color_id(opp),
        }

        result = service.events().insert(
            calendarId=self.calendar_id, body=event
        ).execute()

        logger.info(f"Created deadline event: {result['id']} for {opp.name}")
        return result

    def create_event_range(
        self,
        opp: Opportunity,
        start: datetime,
        end: datetime,
    ) -> dict:
        """Create a calendar event for the actual event/conference."""
        service = self._get_service()

        event = {
            "summary": opp.name,
            "description": self._build_description(opp, "Event"),
            "location": opp.location,
            "start": {
                "date": start.strftime("%Y-%m-%d"),
                "timeZone": opp.timezone,
            },
            "end": {
                "date": (end + timedelta(days=1)).strftime("%Y-%m-%d"),  # End date is exclusive
                "timeZone": opp.timezone,
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60 * 24 * 14},  # 2 weeks
                    {"method": "popup", "minutes": 60 * 24 * 7},   # 1 week
                ],
            },
            "colorId": self._get_color_id(opp),
        }

        result = service.events().insert(
            calendarId=self.calendar_id, body=event
        ).execute()

        logger.info(f"Created event: {result['id']} for {opp.name}")
        return result

    def update_event(self, event_id: str, updates: dict) -> dict:
        """Update an existing calendar event."""
        service = self._get_service()

        # Get existing event
        event = service.events().get(
            calendarId=self.calendar_id, eventId=event_id
        ).execute()

        # Apply updates
        event.update(updates)

        result = service.events().update(
            calendarId=self.calendar_id, eventId=event_id, body=event
        ).execute()

        logger.info(f"Updated event: {event_id}")
        return result

    def delete_event(self, event_id: str) -> None:
        """Delete a calendar event."""
        service = self._get_service()
        service.events().delete(
            calendarId=self.calendar_id, eventId=event_id
        ).execute()
        logger.info(f"Deleted event: {event_id}")

    def sync_opportunity(self, opp: Opportunity) -> List[str]:
        """
        Sync an opportunity to Google Calendar.
        Returns list of created/updated event IDs.
        """
        event_ids = []

        # Create deadline events
        if opp.cfp_deadline:
            try:
                result = self.create_deadline_event(opp, opp.cfp_deadline, "CFP Deadline")
                event_ids.append(result["id"])
            except Exception as e:
                logger.error(f"Failed to create CFP deadline event for {opp.name}: {e}")

        if opp.application_deadline:
            try:
                result = self.create_deadline_event(opp, opp.application_deadline, "Application Deadline")
                event_ids.append(result["id"])
            except Exception as e:
                logger.error(f"Failed to create application deadline event for {opp.name}: {e}")

        if opp.registration_deadline:
            try:
                result = self.create_deadline_event(opp, opp.registration_deadline, "Registration Deadline")
                event_ids.append(result["id"])
            except Exception as e:
                logger.error(f"Failed to create registration deadline event for {opp.name}: {e}")

        # Create event range
        if opp.event_start:
            try:
                end = opp.event_end or opp.event_start
                result = self.create_event_range(opp, opp.event_start, end)
                event_ids.append(result["id"])
            except Exception as e:
                logger.error(f"Failed to create event for {opp.name}: {e}")

        return event_ids

    def sync_all(self, opportunities: List[Opportunity], storage=None) -> dict:
        """
        Sync all opportunities to Google Calendar.
        Returns stats dict.
        """
        stats = {"created": 0, "errors": 0, "skipped": 0}

        for opp in opportunities:
            # Skip if already synced
            if opp.google_event_ids:
                stats["skipped"] += 1
                continue

            try:
                event_ids = self.sync_opportunity(opp)
                if event_ids:
                    opp.google_event_ids = event_ids
                    opp.status = "synced"
                    if storage:
                        storage.update(opp)
                    stats["created"] += len(event_ids)
            except Exception as e:
                logger.error(f"Failed to sync {opp.name}: {e}")
                stats["errors"] += 1

        return stats

    def _build_description(self, opp: Opportunity, event_type: str) -> str:
        """Build event description from opportunity."""
        lines = [
            f"Type: {opp.type.value if hasattr(opp.type, 'value') else opp.type}",
            f"Organizer: {opp.organizer}",
            f"URL: {opp.url}",
            "",
        ]

        if opp.notes:
            lines.append(f"Notes: {opp.notes}")
            lines.append("")

        if opp.materials_checklist:
            lines.append("Materials Checklist:")
            for item, done in opp.materials_checklist.items():
                status = "[x]" if done else "[ ]"
                lines.append(f"  {status} {item.replace('_', ' ').title()}")

        lines.append("")
        lines.append(f"Source: {opp.source}")
        lines.append(f"Progress: {opp.progress_percent}%")
        lines.append(f"RAG Status: {opp.rag_status.value if hasattr(opp.rag_status, 'value') else opp.rag_status}")

        return "\n".join(lines)

    def _get_color_id(self, opp: Opportunity) -> str:
        """Get calendar color ID based on opportunity type."""
        # Google Calendar color IDs: 1-11
        color_map = {
            OpportunityType.CONFERENCE: "9",    # Blue
            OpportunityType.WORKSHOP: "7",      # Cyan
            OpportunityType.SUMMIT: "5",        # Yellow
            OpportunityType.ACCELERATOR: "10",  # Green
            OpportunityType.INCUBATOR: "10",    # Green
            OpportunityType.GRANT: "6",         # Orange
            OpportunityType.COMPETITION: "11",  # Red
        }
        return color_map.get(opp.type, "1")  # Default: Lavender
