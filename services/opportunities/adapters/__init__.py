"""
Source adapters for discovering opportunities.
"""

from .base import BaseAdapter
from .mlsys import MLSysAdapter
from .fmsys import FMSysAdapter
from .summit import AIMfgSummitAdapter
from .accelerators import AcceleratorsAdapter

ALL_ADAPTERS = [
    MLSysAdapter,
    FMSysAdapter,
    AIMfgSummitAdapter,
    AcceleratorsAdapter,
]

__all__ = [
    "BaseAdapter",
    "MLSysAdapter",
    "FMSysAdapter",
    "AIMfgSummitAdapter",
    "AcceleratorsAdapter",
    "ALL_ADAPTERS",
]
