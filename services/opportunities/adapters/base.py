"""
Base adapter class for opportunity sources.
"""

import logging
from abc import ABC, abstractmethod
from typing import List

import httpx

from ..models import Opportunity

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """Base class for opportunity source adapters."""

    name: str = "base"
    source_url: str = ""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch_html(self, url: str) -> str:
        """Fetch HTML content from URL."""
        try:
            response = self.client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FactoryLM-OppsBot/1.0"
            })
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise

    @abstractmethod
    def fetch(self) -> List[Opportunity]:
        """Fetch opportunities from the source. Must be implemented by subclasses."""
        pass

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
