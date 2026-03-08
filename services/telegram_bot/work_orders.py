"""
Work order lifecycle — create, track, close.
V1: in-memory store with optional Matrix API persistence.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Simple incrementing counter (resets on restart — fine for v1)
_wo_counter = 2800


@dataclass
class WorkOrder:
    wo_id: str
    user_id: str
    fault_code: str
    description: str
    created_at: float = field(default_factory=time.time)
    closed_at: Optional[float] = None
    root_cause: Optional[str] = None
    status: str = "open"


class WorkOrderStore:
    """In-memory work order tracker. One open WO per user at a time."""

    def __init__(self):
        self._orders: Dict[str, WorkOrder] = {}  # wo_id -> WorkOrder
        self._user_open: Dict[str, str] = {}     # user_id -> wo_id (open only)

    def create(self, user_id: str, fault_code: str, description: str) -> WorkOrder:
        global _wo_counter
        _wo_counter += 1
        wo_id = f"WO-{_wo_counter}"

        # Close any existing open WO for this user
        if user_id in self._user_open:
            self.close(self._user_open[user_id], "Superseded by new work order")

        wo = WorkOrder(
            wo_id=wo_id,
            user_id=user_id,
            fault_code=fault_code,
            description=description,
        )
        self._orders[wo_id] = wo
        self._user_open[user_id] = wo_id
        logger.info("Created %s for user %s: %s", wo_id, user_id, fault_code)
        return wo

    def close(self, wo_id: str, root_cause: str) -> Optional[WorkOrder]:
        wo = self._orders.get(wo_id)
        if not wo or wo.status != "open":
            return None

        wo.status = "closed"
        wo.closed_at = time.time()
        wo.root_cause = root_cause
        self._user_open.pop(wo.user_id, None)
        logger.info("Closed %s: %s", wo_id, root_cause)
        return wo

    def get_open(self, user_id: str) -> Optional[WorkOrder]:
        wo_id = self._user_open.get(user_id)
        if wo_id:
            return self._orders.get(wo_id)
        return None

    def format_open_wo(self, user_id: str) -> Optional[str]:
        wo = self.get_open(user_id)
        if not wo:
            return None
        elapsed = int(time.time() - wo.created_at)
        mins = elapsed // 60
        return (
            f"{wo.wo_id} | {wo.fault_code} | {wo.description} | "
            f"Open {mins}m"
        )
