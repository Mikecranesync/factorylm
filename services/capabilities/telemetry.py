"""
Telemetry Capability - Sentry + Honeycomb
=========================================
Bulletproof observability with dual backends.
"""

import os
import sys
import json
import time
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from pathlib import Path
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)

# Local trace storage
TRACES_DIR = Path(__file__).parent.parent.parent / "traces"
TRACES_DIR.mkdir(exist_ok=True)


class TelemetryCapability:
    """
    Bulletproof observability.

    Priority:
    1. Sentry - Errors, performance, user tracking
    2. Honeycomb - Deep distributed traces
    3. Local files - Backup when cloud fails
    """

    def __init__(self, service_name: str = "factorylm"):
        self.service_name = service_name
        self.sentry_enabled = False
        self.honeycomb_enabled = False
        self._spans = []
        self._sentry = None
        self._otel_tracer = None

        # Initialize backends
        self._init_sentry()
        self._init_honeycomb()

    def _init_sentry(self):
        """Initialize Sentry."""
        dsn = os.getenv("SENTRY_DSN")
        if not dsn:
            logger.debug("SENTRY_DSN not set - Sentry disabled")
            return

        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_sdk.init(
                dsn=dsn,
                traces_sample_rate=1.0,
                profiles_sample_rate=1.0,
                environment=os.getenv("ENVIRONMENT", "production"),
                release=f"{self.service_name}@1.0.0",
                send_default_pii=True,
                integrations=[
                    LoggingIntegration(
                        level=logging.INFO,
                        event_level=logging.ERROR
                    ),
                ],
                attach_stacktrace=True,
                include_local_variables=True,
            )

            self._sentry = sentry_sdk
            self.sentry_enabled = True
            logger.info("Sentry initialized")

        except ImportError:
            logger.debug("Sentry SDK not installed")
        except Exception as e:
            logger.error(f"Sentry init failed: {e}")

    def _init_honeycomb(self):
        """Initialize Honeycomb via OpenTelemetry."""
        api_key = os.getenv("HONEYCOMB_API_KEY")
        if not api_key:
            logger.debug("HONEYCOMB_API_KEY not set - Honeycomb disabled")
            return

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create({
                "service.name": self.service_name,
                "service.version": "1.0.0",
                "deployment.environment": os.getenv("ENVIRONMENT", "production"),
            })

            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(
                endpoint="https://api.honeycomb.io/v1/traces",
                headers={"x-honeycomb-team": api_key}
            )

            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)

            self._otel_tracer = trace.get_tracer(self.service_name)
            self.honeycomb_enabled = True
            logger.info("Honeycomb OTEL initialized")

        except ImportError:
            logger.debug("OTEL packages not installed")
        except Exception as e:
            logger.error(f"Honeycomb init failed: {e}")

    def health(self) -> dict:
        """Check telemetry health."""
        return {
            "status": "ok",
            "sentry": self.sentry_enabled,
            "honeycomb": self.honeycomb_enabled,
            "local": True,
            "spans_recorded": len(self._spans),
        }

    def set_user(self, user_id: int, username: str = None, extras: Dict = None):
        """Set user context for all events."""
        if self.sentry_enabled:
            self._sentry.set_user({
                "id": str(user_id),
                "username": username or f"user_{user_id}",
                **(extras or {})
            })

    def set_tag(self, key: str, value: str):
        """Set a tag on all future events."""
        if self.sentry_enabled:
            self._sentry.set_tag(key, value)

    def add_breadcrumb(self, message: str, category: str = "custom", level: str = "info", data: Dict = None):
        """Add breadcrumb for debugging."""
        if self.sentry_enabled:
            self._sentry.add_breadcrumb(
                message=message,
                category=category,
                level=level,
                data=data or {}
            )

    @contextmanager
    def span(self, name: str, attributes: Dict[str, Any] = None):
        """
        Create a traced span.

        Usage:
            with telemetry.span("process_command", {"intent": "screenshot"}) as span:
                span.set_attribute("node", "plc-laptop")
                result = do_work()
        """
        start_time = time.time()
        span_data = {
            "trace_id": self._generate_id(),
            "span_id": self._generate_id(),
            "name": name,
            "start_time": start_time,
            "attributes": attributes or {},
            "status": "OK",
            "error": None
        }

        # Sentry span
        sentry_span = None
        if self.sentry_enabled:
            try:
                sentry_span = self._sentry.start_span(op=name, description=name)
                if attributes:
                    for k, v in attributes.items():
                        sentry_span.set_data(k, v)
            except Exception:
                pass

        # Honeycomb span
        otel_span = None
        if self._otel_tracer:
            try:
                otel_span = self._otel_tracer.start_span(name)
                if attributes:
                    for k, v in attributes.items():
                        otel_span.set_attribute(k, str(v) if not isinstance(v, (str, int, float, bool)) else v)
            except Exception:
                pass

        class SpanContext:
            def __init__(ctx_self):
                ctx_self.attributes = span_data["attributes"]

            def set_attribute(ctx_self, key: str, value: Any):
                ctx_self.attributes[key] = value
                if sentry_span:
                    try:
                        sentry_span.set_data(key, value)
                    except Exception:
                        pass
                if otel_span:
                    try:
                        otel_span.set_attribute(key, str(value) if not isinstance(value, (str, int, float, bool)) else value)
                    except Exception:
                        pass

        ctx = SpanContext()

        try:
            yield ctx
            span_data["status"] = "OK"
        except Exception as e:
            span_data["status"] = "ERROR"
            span_data["error"] = str(e)
            if self.sentry_enabled:
                self._sentry.capture_exception(e)
            raise
        finally:
            span_data["end_time"] = time.time()
            span_data["duration_ms"] = (span_data["end_time"] - start_time) * 1000
            span_data["attributes"] = ctx.attributes

            if sentry_span:
                try:
                    if span_data["status"] == "ERROR":
                        sentry_span.set_status("internal_error")
                    sentry_span.finish()
                except Exception:
                    pass

            if otel_span:
                try:
                    from opentelemetry.trace import Status, StatusCode
                    if span_data["status"] == "ERROR":
                        otel_span.set_status(Status(StatusCode.ERROR, span_data["error"]))
                    otel_span.end()
                except Exception:
                    pass

            self._record_span(span_data)

    def capture_exception(self, exception: Exception = None, extras: Dict = None):
        """Capture exception to all backends."""
        if exception is None:
            exception = sys.exc_info()[1]

        if self.sentry_enabled:
            with self._sentry.push_scope() as scope:
                if extras:
                    for k, v in extras.items():
                        scope.set_extra(k, v)
                self._sentry.capture_exception(exception)

        tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
        self._write_trace({
            "type": "exception",
            "timestamp": datetime.now().isoformat(),
            "exception": str(exception),
            "traceback": "".join(tb),
            "extras": extras or {}
        })

        logger.error(f"Exception captured: {exception}", exc_info=True)

    def capture_message(self, message: str, level: str = "info", extras: Dict = None):
        """Capture message to all backends."""
        if self.sentry_enabled:
            with self._sentry.push_scope() as scope:
                if extras:
                    for k, v in extras.items():
                        scope.set_extra(k, v)
                self._sentry.capture_message(message, level=level)

        self._write_trace({
            "type": "message",
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "extras": extras or {}
        })

        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(log_level, message)

    def _generate_id(self) -> str:
        """Generate random ID."""
        import uuid
        return uuid.uuid4().hex[:16]

    def _record_span(self, span_data: Dict):
        """Record span to local backends."""
        self._spans.append(span_data)
        if len(self._spans) > 1000:
            self._spans = self._spans[-500:]

        logger.info(f"SPAN: {span_data['name']} ({span_data.get('duration_ms', 0):.1f}ms) [{span_data['status']}]")
        self._write_trace(span_data)

    def _write_trace(self, data: Dict):
        """Write trace to daily file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        trace_file = TRACES_DIR / f"{date_str}.jsonl"

        try:
            with open(trace_file, "a") as f:
                f.write(json.dumps(data, default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write trace: {e}")

    def get_stats(self) -> Dict:
        """Get telemetry statistics."""
        if not self._spans:
            return {
                "total_spans": 0,
                "sentry_enabled": self.sentry_enabled,
                "honeycomb_enabled": self.honeycomb_enabled,
            }

        durations = [s.get("duration_ms", 0) for s in self._spans if s.get("duration_ms")]
        errors = [s for s in self._spans if s.get("status") == "ERROR"]

        return {
            "total_spans": len(self._spans),
            "error_count": len(errors),
            "error_rate": len(errors) / len(self._spans) if self._spans else 0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "sentry_enabled": self.sentry_enabled,
            "honeycomb_enabled": self.honeycomb_enabled,
        }

    def get_recent_spans(self, limit: int = 50) -> list:
        """Get recent spans."""
        return self._spans[-limit:]

    def flush(self):
        """Flush all pending telemetry."""
        if self.sentry_enabled:
            try:
                self._sentry.flush(timeout=5.0)
            except Exception:
                pass


def traced(name: str = None, attributes: Dict = None):
    """Decorator to automatically trace a function."""
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with get_telemetry().span(span_name, attributes) as span:
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with get_telemetry().span(span_name, attributes) as span:
                return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Global instance
_telemetry: Optional[TelemetryCapability] = None


def get_telemetry() -> TelemetryCapability:
    """Get the global telemetry instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetryCapability()
    return _telemetry
