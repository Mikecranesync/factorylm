"""
observability — FactoryLM tracing & metrics helpers.

Re-exports the core decorators so workers can do::

    from observability import traced, track_llm_call, track_api_call
"""

import functools
import logging
import time
import uuid
from contextvars import ContextVar

log = logging.getLogger("factorylm.observability")

LANGFUSE_ENABLED = False
_trace_id: ContextVar[str | None] = ContextVar("factorylm_trace_id", default=None)


class TraceContext:
    """Minimal trace context used by existing Celery workers."""

    @staticmethod
    def set(*, trace_id: str) -> None:
        _trace_id.set(trace_id)

    @staticmethod
    def clear() -> None:
        _trace_id.set(None)


def generate_trace_id() -> str:
    return uuid.uuid4().hex


def get_trace_id_from_context() -> str | None:
    return _trace_id.get()


def _log_trace(**_kwargs) -> None:
    """Compatibility hook for workers until a tracing backend is configured."""


# ---------------------------------------------------------------------------
# traced — identity decorator that logs entry/exit at DEBUG level
# ---------------------------------------------------------------------------

def traced(fn=None, *, name: str | None = None, **_kw):
    """Identity decorator — logs entry/exit at DEBUG level.

    Accepts (and ignores) arbitrary keyword args so call sites that pass
    ``layer=`` or ``span_name=`` still work without changes.
    """
    def decorator(func):
        span_name = name or func.__qualname__

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            log.debug("TRACE START %s", span_name)
            t0 = time.monotonic()
            try:
                return func(*args, **kwargs)
            finally:
                log.debug("TRACE END   %s  %.3fs", span_name, time.monotonic() - t0)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            log.debug("TRACE START %s", span_name)
            t0 = time.monotonic()
            try:
                return await func(*args, **kwargs)
            finally:
                log.debug("TRACE END   %s  %.3fs", span_name, time.monotonic() - t0)

        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator(fn) if fn is not None else decorator


# ---------------------------------------------------------------------------
# Tracking helpers — no-op stubs until a real backend is wired
# ---------------------------------------------------------------------------

def track_llm_call(provider: str, model: str, tokens: int = 0, latency_ms: float = 0):
    """Record an LLM API call — no-op until a real backend is wired."""
    log.debug("LLM call  provider=%s model=%s tokens=%d latency=%.0fms",
              provider, model, tokens, latency_ms)


def track_api_call(endpoint: str, status: int = 200, latency_ms: float = 0):
    """Record an HTTP API call — no-op until a real backend is wired."""
    log.debug("API call  endpoint=%s status=%d latency=%.0fms",
              endpoint, status, latency_ms)
