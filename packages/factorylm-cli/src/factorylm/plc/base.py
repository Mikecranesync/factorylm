"""Abstract base class for PLC clients."""

from abc import ABC, abstractmethod
from typing import Any


class BasePLCClient(ABC):
    """Interface that all PLC drivers implement."""

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the PLC.  Returns True on success."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if currently connected."""
        ...

    @abstractmethod
    def read_tags(self) -> dict[str, Any]:
        """Read all configured tags. Returns {tag_name: value}."""
        ...

    @abstractmethod
    def write_tag(self, name: str, value: Any) -> bool:
        """Write a single tag value. Returns True on success."""
        ...

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
