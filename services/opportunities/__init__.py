"""
Factory Opportunities Service

Discovers AI/ML/robotics/manufacturing programs and events,
stores them in SQLite, and syncs deadlines to Google Calendar.

Runs TWICE DAILY at 8am and 8pm.
"""

from .models import Opportunity, OpportunityType, OpportunityStatus, RAGStatus
from .storage import OpportunitiesStorage

__all__ = [
    "Opportunity",
    "OpportunityType",
    "OpportunityStatus",
    "RAGStatus",
    "OpportunitiesStorage",
]
