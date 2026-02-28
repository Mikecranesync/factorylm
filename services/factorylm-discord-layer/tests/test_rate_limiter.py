"""Tests for the webhook rate limiter."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from factorylm.relay.rate_limiter import QueueItem, TokenBucket, WebhookRateLimiter


class TestTokenBucket:
    def test_initial_tokens(self):
        bucket = TokenBucket(capacity=5, refill_period=2.0)
        assert bucket.tokens == 5.0

    def test_acquire_returns_zero_when_available(self):
        bucket = TokenBucket(capacity=5)
        wait = bucket.acquire()
        assert wait == 0.0
        assert bucket.tokens == 4.0

    def test_acquire_drains_tokens(self):
        bucket = TokenBucket(capacity=3)
        for _ in range(3):
            assert bucket.acquire() == 0.0
        # 4th acquire should need to wait
        wait = bucket.acquire()
        assert wait > 0.0

    def test_acquire_wait_time_positive(self):
        bucket = TokenBucket(capacity=1, refill_period=1.0)
        bucket.acquire()  # drain the single token
        wait = bucket.acquire()
        assert wait > 0.0
        assert wait <= 1.0

    def test_update_from_headers(self):
        bucket = TokenBucket(capacity=5)
        bucket.tokens = 0  # drain
        bucket.update_from_headers(remaining=3, reset_after=1.5)
        assert bucket.tokens == 3.0

    def test_update_from_headers_caps_at_capacity(self):
        bucket = TokenBucket(capacity=5)
        bucket.update_from_headers(remaining=10, reset_after=1.0)
        assert bucket.tokens == 5.0


class TestWebhookRateLimiter:
    @pytest.fixture
    def limiter(self):
        return WebhookRateLimiter(max_queue_size=5)

    @pytest.mark.asyncio
    async def test_post_message_queues(self, limiter):
        url = "https://discord.com/api/webhooks/1/abc"
        payload = {"content": "test"}

        with patch.object(limiter, "_drain_worker", new_callable=AsyncMock):
            result = await limiter.post_message(url, payload)

        assert result is True
        assert limiter.queue_depth(url) == 1

    @pytest.mark.asyncio
    async def test_queue_eviction_drops_oldest(self, limiter):
        url = "https://discord.com/api/webhooks/1/abc"

        with patch.object(limiter, "_drain_worker", new_callable=AsyncMock):
            # Fill the queue (maxsize=5)
            for i in range(5):
                await limiter.post_message(url, {"content": f"msg{i}"})

            assert limiter.queue_depth(url) == 5

            # Post one more — should evict oldest
            result = await limiter.post_message(url, {"content": "msg5"})
            assert result is True
            assert limiter.queue_depth(url) == 5  # still 5, oldest dropped

    @pytest.mark.asyncio
    async def test_total_queue_depth(self, limiter):
        url1 = "https://discord.com/api/webhooks/1/abc"
        url2 = "https://discord.com/api/webhooks/2/def"

        with patch.object(limiter, "_drain_worker", new_callable=AsyncMock):
            await limiter.post_message(url1, {"content": "a"})
            await limiter.post_message(url1, {"content": "b"})
            await limiter.post_message(url2, {"content": "c"})

        assert limiter.total_queue_depth() == 3

    @pytest.mark.asyncio
    async def test_queue_depth_zero_for_unknown(self, limiter):
        assert limiter.queue_depth("https://unknown.com") == 0

    @pytest.mark.asyncio
    async def test_drain_worker_posts_messages(self, limiter):
        url = "https://discord.com/api/webhooks/1/abc"
        queue = limiter._get_queue(url)
        await queue.put(QueueItem(webhook_url=url, payload={"content": "test"}))

        with patch.object(
            limiter, "_do_post", new_callable=AsyncMock, return_value=True
        ) as mock_post:
            await limiter._drain_worker(url)

        mock_post.assert_called_once_with(
            url, {"content": "test"}, limiter._get_bucket(url)
        )

    @pytest.mark.asyncio
    async def test_do_post_success(self, limiter):
        bucket = TokenBucket()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {
            "X-RateLimit-Remaining": "4",
            "X-RateLimit-Reset-After": "1.5",
        }

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            yield mock_resp

        mock_session = MagicMock()
        mock_session.post = mock_post

        with patch.object(
            limiter, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            result = await limiter._do_post(
                "https://example.com/hook", {"content": "test"}, bucket
            )
        assert result is True
        assert bucket.tokens == 4.0

    @pytest.mark.asyncio
    async def test_do_post_429_retry(self, limiter):
        bucket = TokenBucket()

        mock_resp_429 = MagicMock()
        mock_resp_429.status = 429
        mock_resp_429.headers = {"Retry-After": "0.01", "X-RateLimit-Reset-After": "0.01"}

        mock_resp_200 = MagicMock()
        mock_resp_200.status = 200
        mock_resp_200.headers = {"X-RateLimit-Remaining": "4", "X-RateLimit-Reset-After": "2.0"}

        responses = iter([mock_resp_429, mock_resp_200])
        call_count = 0

        @asynccontextmanager
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            yield next(responses)

        mock_session = MagicMock()
        mock_session.post = mock_post

        with patch.object(
            limiter, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            result = await limiter._do_post(
                "https://example.com/hook", {"content": "test"}, bucket
            )
        assert result is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_close(self, limiter):
        limiter._session = AsyncMock()
        limiter._session.closed = False
        await limiter.close()
        limiter._session.close.assert_called_once()
