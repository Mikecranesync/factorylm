"""
observability — FactoryLM tracing & metrics helpers.

Re-exports the core decorators so workers can do::

    from observability import traced, track_llm_call, track_api_call
"""

import functools
import logging
import time

log = logging.getLogger("factorylm.observability")


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
