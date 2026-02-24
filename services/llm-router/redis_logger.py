"""Redis logger — log every LLM call for observability."""

from __future__ import annotations

import logging
import time
from datetime import date

logger = logging.getLogger("llm-router.redis")

# Prefix for all keys
_PREFIX = "llm-router"


class RedisLogger:
    """Async Redis logger for LLM router telemetry."""

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._redis = None
        self._redis_url = redis_url

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()
            logger.info("Redis connected at %s", self._redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — logging disabled", exc)
            self._redis = None

    async def log_request(
        self,
        provider: str,
        model: str,
        tokens: int,
        latency_ms: int,
        task_type: str | None = None,
    ) -> None:
        if not self._redis:
            return
        try:
            today = str(date.today())
            pipe = self._redis.pipeline()

            # Daily per-provider counters
            daily_key = f"{_PREFIX}:daily:{today}:{provider}"
            pipe.hincrby(daily_key, "requests", 1)
            pipe.hincrby(daily_key, "tokens", tokens)
            pipe.expire(daily_key, 86400 * 7)  # keep 7 days

            # Global totals (lifetime)
            pipe.hincrby(f"{_PREFIX}:totals", f"{provider}:requests", 1)
            pipe.hincrby(f"{_PREFIX}:totals", f"{provider}:tokens", tokens)

            # Latency sorted set (score = latency, member = timestamp:provider)
            member = f"{time.time():.3f}:{provider}"
            pipe.zadd(f"{_PREFIX}:latency", {member: latency_ms})
            # Trim to last 1000 entries
            pipe.zremrangebyrank(f"{_PREFIX}:latency", 0, -1001)

            # Task-type counters
            if task_type:
                pipe.hincrby(f"{_PREFIX}:task_types", task_type, 1)

            await pipe.execute()
        except Exception as exc:
            logger.warning("Redis log failed: %s", exc)

    async def get_stats(self) -> dict:
        """Return aggregated stats for /health/stats."""
        if not self._redis:
            return {"redis": "unavailable"}
        try:
            totals = await self._redis.hgetall(f"{_PREFIX}:totals") or {}
            task_types = await self._redis.hgetall(f"{_PREFIX}:task_types") or {}

            # Recent latency (last 100)
            recent = await self._redis.zrevrange(
                f"{_PREFIX}:latency", 0, 99, withscores=True
            )
            latencies = [score for _, score in recent] if recent else []
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            return {
                "totals": totals,
                "task_types": task_types,
                "avg_latency_ms": round(avg_latency, 1),
                "recent_requests": len(latencies),
            }
        except Exception as exc:
            logger.warning("Redis stats failed: %s", exc)
            return {"redis": "error", "detail": str(exc)}
