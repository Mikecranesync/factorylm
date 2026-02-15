"""
PEPPER Deploy and Versioning System

Atomic deployment, rollback, and state management for PEPPER.
"""

from .versioning import Version, VersionManager
from .deployer import PepperDeployer
from .state import StateManager
from .rollback import RollbackManager

__all__ = [
    'Version',
    'VersionManager',
    'PepperDeployer',
    'StateManager',
    'RollbackManager',
]

__version__ = '1.0.0'
