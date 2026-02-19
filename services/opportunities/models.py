"""
Opportunity data models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid


class OpportunityType(str, Enum):
    CONFERENCE = "conference"
    WORKSHOP = "workshop"
    SUMMIT = "summit"
    ACCELERATOR = "accelerator"
    INCUBATOR = "incubator"
    GRANT = "grant"
    COMPETITION = "competition"


class OpportunityStatus(str, Enum):
    DISCOVERED = "discovered"
    PARSED = "parsed"
    SYNCED = "synced"
    TRACKING = "tracking"
    EXPIRED = "expired"
    SUBMITTED = "submitted"


class RAGStatus(str, Enum):
    """Progress tracking status using RAG (Red/Amber/Green) system."""
    GREEN = "green"    # On track: >50% complete with >14 days remaining
    YELLOW = "yellow"  # At risk: <50% complete OR <14 days remaining
    RED = "red"        # Behind: <25% complete OR <7 days remaining
    GREY = "grey"      # No deadline or not applicable


@dataclass
class Opportunity:
    """Represents an AI/ML/robotics/manufacturing opportunity."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    organizer: str = ""
    type: OpportunityType = OpportunityType.CONFERENCE
    url: str = ""

    # Deadlines
    cfp_deadline: Optional[datetime] = None
    application_deadline: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None

    # Event dates
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None

    # Location
    timezone: str = "America/New_York"
    location: str = ""
    is_virtual: bool = False

    # Source tracking
    source: str = ""  # mlsys, fmsys, summit, accelerator
    source_url: str = ""

    # Status and sync
    status: OpportunityStatus = OpportunityStatus.DISCOVERED
    google_event_ids: List[str] = field(default_factory=list)

    # Progress tracking
    progress_percent: int = 0  # 0-100
    rag_status: RAGStatus = RAGStatus.GREY
    materials_checklist: dict = field(default_factory=dict)
    # Example: {"paper_draft": False, "application_form": True, "video_pitch": False}

    # Metadata
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def get_primary_deadline(self) -> Optional[datetime]:
        """Get the most relevant deadline for this opportunity."""
        if self.type in (OpportunityType.CONFERENCE, OpportunityType.WORKSHOP):
            return self.cfp_deadline or self.registration_deadline
        elif self.type in (OpportunityType.ACCELERATOR, OpportunityType.INCUBATOR, OpportunityType.GRANT):
            return self.application_deadline
        return self.registration_deadline or self.event_start

    def days_until_deadline(self) -> Optional[int]:
        """Calculate days remaining until primary deadline."""
        deadline = self.get_primary_deadline()
        if not deadline:
            return None
        delta = deadline - datetime.utcnow()
        return delta.days

    def calculate_rag_status(self) -> RAGStatus:
        """Calculate RAG status based on progress and days remaining."""
        days = self.days_until_deadline()
        if days is None:
            return RAGStatus.GREY

        # RED: Behind - <25% complete OR <7 days remaining
        if self.progress_percent < 25 or days < 7:
            return RAGStatus.RED

        # YELLOW: At risk - <50% complete OR <14 days remaining
        if self.progress_percent < 50 or days < 14:
            return RAGStatus.YELLOW

        # GREEN: On track - >50% complete with >14 days remaining
        return RAGStatus.GREEN

    def update_rag_status(self) -> None:
        """Update the RAG status based on current progress."""
        self.rag_status = self.calculate_rag_status()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "organizer": self.organizer,
            "type": self.type.value if isinstance(self.type, OpportunityType) else self.type,
            "url": self.url,
            "cfp_deadline": self.cfp_deadline.isoformat() if self.cfp_deadline else None,
            "application_deadline": self.application_deadline.isoformat() if self.application_deadline else None,
            "registration_deadline": self.registration_deadline.isoformat() if self.registration_deadline else None,
            "event_start": self.event_start.isoformat() if self.event_start else None,
            "event_end": self.event_end.isoformat() if self.event_end else None,
            "timezone": self.timezone,
            "location": self.location,
            "is_virtual": self.is_virtual,
            "source": self.source,
            "source_url": self.source_url,
            "status": self.status.value if isinstance(self.status, OpportunityStatus) else self.status,
            "google_event_ids": ",".join(self.google_event_ids),
            "progress_percent": self.progress_percent,
            "rag_status": self.rag_status.value if isinstance(self.rag_status, RAGStatus) else self.rag_status,
            "materials_checklist": str(self.materials_checklist),
            "notes": self.notes,
            "tags": ",".join(self.tags),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Opportunity":
        """Create from dictionary (from storage)."""
        def parse_datetime(val):
            if val is None or val == "":
                return None
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(val)

        def parse_list(val):
            if not val:
                return []
            if isinstance(val, list):
                return val
            return [x.strip() for x in val.split(",") if x.strip()]

        def parse_dict(val):
            if not val:
                return {}
            if isinstance(val, dict):
                return val
            try:
                import ast
                return ast.literal_eval(val)
            except:
                return {}

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            organizer=data.get("organizer", ""),
            type=OpportunityType(data["type"]) if data.get("type") else OpportunityType.CONFERENCE,
            url=data.get("url", ""),
            cfp_deadline=parse_datetime(data.get("cfp_deadline")),
            application_deadline=parse_datetime(data.get("application_deadline")),
            registration_deadline=parse_datetime(data.get("registration_deadline")),
            event_start=parse_datetime(data.get("event_start")),
            event_end=parse_datetime(data.get("event_end")),
            timezone=data.get("timezone", "America/New_York"),
            location=data.get("location", ""),
            is_virtual=bool(data.get("is_virtual", False)),
            source=data.get("source", ""),
            source_url=data.get("source_url", ""),
            status=OpportunityStatus(data["status"]) if data.get("status") else OpportunityStatus.DISCOVERED,
            google_event_ids=parse_list(data.get("google_event_ids")),
            progress_percent=int(data.get("progress_percent", 0)),
            rag_status=RAGStatus(data["rag_status"]) if data.get("rag_status") else RAGStatus.GREY,
            materials_checklist=parse_dict(data.get("materials_checklist")),
            notes=data.get("notes", ""),
            tags=parse_list(data.get("tags")),
            created_at=parse_datetime(data.get("created_at")) or datetime.utcnow(),
            updated_at=parse_datetime(data.get("updated_at")) or datetime.utcnow(),
        )
