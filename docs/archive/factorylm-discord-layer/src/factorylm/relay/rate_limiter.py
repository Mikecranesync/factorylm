"""Token bucket rate limiter with per-webhook queues.

Handles Discord webhook rate limits:
- Token bucket: 5 requests / 2 seconds per webhook URL
- Per-webhook asyncio.Queue(maxsize=500)
- Parses X-RateLimit-Remaining + X-RateLimit-Reset from Discord responses
- Drops oldest message when queue full, logs WARNING
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Simple token bucket for rate limiting."""

    capacity: int = 5
    refill_period: float = 2.0
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        new_tokens = elapsed * (self.capacity / self.refill_period)
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now

    def acquire(self) -> float:
        """Try to acquire a token. Returns seconds to wait (0 if available)."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return 0.0
        # Calculate wait time for next token
        deficit = 1.0 - self.tokens
        wait = deficit * (self.refill_period / self.capacity)
        return wait

    def update_from_headers(self, remaining: int, reset_after: float) -> None:
        """Update bucket state from Discord rate limit headers."""
        self.tokens = min(self.capacity, float(remaining))
        if reset_after > 0:
            self.last_refill = time.monotonic() - (self.refill_period - reset_after)


@dataclass
class QueueItem:
    """A queued webhook payload."""

    webhook_url: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.monotonic)


class WebhookRateLimiter:
    """Rate-limited webhook posting with per-URL queues."""

    def __init__(self, max_queue_size: int = 500) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._queues: dict[str, asyncio.Queue[QueueItem]] = {}
        self._max_queue_size = max_queue_size
        self._session: aiohttp.ClientSession | None = None
        self._workers: dict[str, asyncio.Task] = {}
        self._running = False

    def _get_bucket(self, webhook_url: str) -> TokenBucket:
        if webhook_url not in self._buckets:
            self._buckets[webhook_url] = TokenBucket()
        return self._buckets[webhook_url]

    def _get_queue(self, webhook_url: str) -> asyncio.Queue[QueueItem]:
        if webhook_url not in self._queues:
            self._queues[webhook_url] = asyncio.Queue(maxsize=self._max_queue_size)
        return self._queues[webhook_url]

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def post_message(self, webhook_url: str, payload: dict[str, Any]) -> bool:
        """Queue a message for rate-limited delivery.

        Returns True if queued, False if queue is full (oldest dropped).
        """
        queue = self._get_queue(webhook_url)
        item = QueueItem(webhook_url=webhook_url, payload=payload)

        if queue.full():
            # Drop oldest (not newest) — get from front, put new at back
            try:
                dropped = queue.get_nowait()
                logger.warning(
                    "Queue full for webhook, dropping oldest message (age=%.1fs)",
                    time.monotonic() - dropped.timestamp,
                )
                queue.task_done()
            except asyncio.QueueEmpty:
                pass

        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.error("Queue still full after eviction attempt")
            return False

        # Ensure drain worker is running for this URL
        if webhook_url not in self._workers or self._workers[webhook_url].done():
            self._workers[webhook_url] = asyncio.create_task(
                self._drain_worker(webhook_url)
            )

        return True

    async def _drain_worker(self, webhook_url: str) -> None:
        """Background task: pull from queue, respect rate limits, post to webhook."""
        queue = self._get_queue(webhook_url)
        bucket = self._get_bucket(webhook_url)

        while not queue.empty():
            item = await queue.get()

            # Wait for rate limit token
            wait = bucket.acquire()
            if wait > 0:
                await asyncio.sleep(wait)

            success = await self._do_post(webhook_url, item.payload, bucket)
            if not success:
                logger.warning("Failed to post to webhook, message dropped")

            queue.task_done()

    async def _do_post(
        self, webhook_url: str, payload: dict[str, Any], bucket: TokenBucket
    ) -> bool:
        """Actually POST to the webhook, handling 429 retries."""
        session = await self._get_session()

        for attempt in range(3):
            try:
                async with session.post(webhook_url, json=payload) as resp:
                    # Parse rate limit headers
                    remaining = resp.headers.get("X-RateLimit-Remaining")
                    reset_after = resp.headers.get("X-RateLimit-Reset-After")
                    if remaining is not None and reset_after is not None:
                        bucket.update_from_headers(
                            int(remaining), float(reset_after)
                        )

                    if resp.status in (200, 204):
                        return True

                    if resp.status == 429:
                        retry_after = float(
                            resp.headers.get("Retry-After", reset_after or "1.0")
                        )
                        logger.warning(
                            "Rate limited (429), retrying in %.1fs (attempt %d/3)",
                            retry_after,
                            attempt + 1,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    logger.warning("Webhook POST returned %s", resp.status)
                    return False
            except Exception:
                logger.exception("Error posting to webhook (attempt %d/3)", attempt + 1)
                if attempt < 2:
                    await asyncio.sleep(0.5)

        return False

    def queue_depth(self, webhook_url: str) -> int:
        """Return current queue depth for a webhook URL."""
        if webhook_url in self._queues:
            return self._queues[webhook_url].qsize()
        return 0

    def total_queue_depth(self) -> int:
        """Return total queue depth across all webhooks."""
        return sum(q.qsize() for q in self._queues.values())

    async def close(self) -> None:
        """Cancel all workers and close the session."""
        for task in self._workers.values():
            task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()
