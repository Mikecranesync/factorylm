"""
FactoryLM Observability — lightweight OpenTelemetry helpers.

    from factorylm.observability import init_tracing, traced, create_span
    init_tracing("plc-modbus")       # one-line init at startup

All helpers are no-ops if OTel packages aren't installed or HONEYCOMB_API_KEY
is not set.  The app will never crash because of missing tracing deps.
"""
from __future__ import annotations

import functools, logging, os
from contextlib import contextmanager
from typing import Any, Dict, Optional

log = logging.getLogger("factorylm.observability")

# -- Globals (set by init_tracing) --
_SERVICE_NAME: str = "factorylm-unknown"
_ENABLED: bool = False
_ENDPOINT: str = ""
_tracer: Any = None

# -- Safe OTel imports --
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

# ── Public API ────────────────────────────────────────────────────────

def init_tracing(service_name: str) -> bool:
    """Initialise OTel tracing with Honeycomb OTLP exporter.  Returns True if enabled."""
    global _SERVICE_NAME, _ENABLED, _ENDPOINT, _tracer
    _SERVICE_NAME = service_name
    api_key = os.environ.get("HONEYCOMB_API_KEY", "")
    if not api_key:
        log.warning("[observability] HONEYCOMB_API_KEY not set — tracing disabled")
        return False
    if not _OTEL_AVAILABLE:
        log.warning("[observability] OTel packages not installed — tracing disabled")
        return False
    try:
        _ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "https://api.honeycomb.io:443")
        env = os.environ.get("OTEL_DEPLOYMENT_ENVIRONMENT", "production")
        resource = Resource.create({
            "service.name": service_name,
            "deployment.environment.name": env,
            "repo.name": "factorylm",
        })
        exporter = OTLPSpanExporter(
            endpoint=f"{_ENDPOINT}/v1/traces",
            headers={"x-honeycomb-team": api_key},
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("factorylm", "0.1.0")
        _ENABLED = True
        log.info(f"[observability] ✓ Tracing started → {_ENDPOINT}  service={service_name}")
        return True
    except Exception as exc:
        log.error(f"[observability] Failed to init tracing: {exc}")
        return False


def tracing_health() -> Dict[str, Any]:
    """Return a dict describing current tracing state (useful for /health endpoints)."""
    return {
        "enabled": _ENABLED,
        "service_name": _SERVICE_NAME,
        "endpoint": _ENDPOINT,
        "otel_packages_installed": _OTEL_AVAILABLE,
    }


def record_event(name: str, attributes: Optional[Dict[str, str]] = None) -> None:
    """Record a structured event on the current span (no-op if tracing disabled)."""
    if not _ENABLED or _tracer is None:
        return
    try:
        span = trace.get_current_span()
        attrs: Dict[str, str] = {
            "service_name": _SERVICE_NAME,
            "repo_name": "factorylm",
            "environment": os.environ.get("OTEL_DEPLOYMENT_ENVIRONMENT", "production"),
        }
        if attributes:
            attrs.update(attributes)
        span.add_event(name, attributes=attrs)
    except Exception:
        pass  # never crash the app


def traced(fn=None, *, span_name: Optional[str] = None):
    """Decorator: wraps a sync or async function in a span.

        @traced
        def sync_work(): ...

        @traced(span_name="custom-name")
        async def async_work(): ...
    """
    def decorator(func):
        _name = span_name or func.__qualname__
        if _is_coroutine(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not _ENABLED or _tracer is None:
                    return await func(*args, **kwargs)
                with _tracer.start_as_current_span(_name):
                    return await func(*args, **kwargs)
            return async_wrapper
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not _ENABLED or _tracer is None:
                return func(*args, **kwargs)
            with _tracer.start_as_current_span(_name):
                return func(*args, **kwargs)
        return sync_wrapper
    if fn is not None:
        return decorator(fn)
    return decorator


@contextmanager
def create_span(name: str, attributes: Optional[Dict[str, str]] = None):
    """Context manager for a manual span."""
    if not _ENABLED or _tracer is None:
        yield None
        return
    try:
        with _tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            yield span
    except Exception:
        yield None


def _is_coroutine(func) -> bool:
    import asyncio
    return asyncio.iscoroutinefunction(func)
