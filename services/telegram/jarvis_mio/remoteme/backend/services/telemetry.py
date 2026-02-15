"""
RemoteMe Telemetry
==================
OpenTelemetry instrumentation with Honeycomb/Sentry export.
Falls back to console/file logging if not configured.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass

logger = logging.getLogger("remoteme.telemetry")

# Trace storage for analysis
TRACES_DIR = Path(__file__).parent.parent.parent / "traces"
TRACES_DIR.mkdir(exist_ok=True)


@dataclass
class Span:
    """Simple span for tracing."""
    trace_id: str
    span_id: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = None
    status: str = "OK"
    error: Optional[str] = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def set_status(self, status: str, error: Optional[str] = None):
        self.status = status
        self.error = error

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "status": self.status,
            "error": self.error
        }


class RemoteMeTracer:
    """
    Tracer for RemoteMe backend.

    Exports to:
    1. Honeycomb (if HONEYCOMB_API_KEY available)
    2. Sentry (if SENTRY_DSN available)
    3. Console (structured JSON)
    4. Local file (traces/{date}.jsonl)
    """

    def __init__(self):
        self.honeycomb_key = os.getenv("HONEYCOMB_API_KEY")
        self.sentry_dsn = os.getenv("SENTRY_DSN")
        self.service_name = "remoteme"
        self._otel_tracer = None
        self._sentry_initialized = False
        self._spans: list[Span] = []

        # Initialize Honeycomb OTEL if available
        if self.honeycomb_key:
            self._init_honeycomb()

        # Initialize Sentry if available
        if self.sentry_dsn:
            self._init_sentry()

        if not self.honeycomb_key and not self.sentry_dsn:
            logger.info("No observability keys found, using local tracing only")

    def _init_honeycomb(self):
        """Initialize OpenTelemetry with Honeycomb exporter."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create({
                "service.name": self.service_name,
                "service.version": "1.0.0",
            })

            provider = TracerProvider(resource=resource)

            exporter = OTLPSpanExporter(
                endpoint="https://api.honeycomb.io/v1/traces",
                headers={
                    "x-honeycomb-team": self.honeycomb_key,
                }
            )

            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            self._otel_tracer = trace.get_tracer(self.service_name)

            logger.info("✓ Honeycomb OTEL tracer initialized")

        except ImportError as e:
            logger.warning(f"OTEL packages not available: {e}")
        except Exception as e:
            logger.error(f"Failed to init Honeycomb OTEL: {e}")

    def _init_sentry(self):
        """Initialize Sentry SDK."""
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.httpx import HttpxIntegration

            sentry_sdk.init(
                dsn=self.sentry_dsn,
                traces_sample_rate=1.0,
                profiles_sample_rate=0.5,
                environment=os.getenv("ENVIRONMENT", "production"),
                integrations=[
                    FastApiIntegration(transaction_style="endpoint"),
                    HttpxIntegration(),
                ],
            )
            self._sentry_initialized = True
            logger.info("✓ Sentry SDK initialized")

        except ImportError as e:
            logger.warning(f"Sentry SDK not available: {e}")
        except Exception as e:
            logger.error(f"Failed to init Sentry: {e}")

    def _generate_id(self) -> str:
        """Generate a random trace/span ID."""
        import uuid
        return uuid.uuid4().hex[:16]

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        Create a tracing span.

        Usage:
            with tracer.span("handle_command", {"user.id": 123}) as span:
                span.set_attribute("llm.model", "llama-3.1-8b")
                # do work
        """
        trace_id = self._generate_id()
        span_id = self._generate_id()

        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            start_time=time.time(),
            attributes=attributes or {}
        )

        # If OTEL available, create real span
        otel_span = None
        if self._otel_tracer:
            try:
                from opentelemetry import trace
                otel_span = self._otel_tracer.start_span(name)
                if attributes:
                    for k, v in attributes.items():
                        otel_span.set_attribute(k, str(v) if not isinstance(v, (str, int, float, bool)) else v)
            except Exception as e:
                logger.debug(f"OTEL span error: {e}")

        # Sentry transaction
        sentry_span = None
        if self._sentry_initialized:
            try:
                import sentry_sdk
                sentry_span = sentry_sdk.start_span(op=name, description=name)
                if attributes:
                    for k, v in attributes.items():
                        sentry_span.set_data(k, v)
            except Exception as e:
                logger.debug(f"Sentry span error: {e}")

        try:
            yield span
            span.status = "OK"
        except Exception as e:
            span.set_status("ERROR", str(e))

            # Report to Sentry
            if self._sentry_initialized:
                try:
                    import sentry_sdk
                    sentry_sdk.capture_exception(e)
                except Exception:
                    pass
            raise
        finally:
            span.end_time = time.time()

            # End OTEL span
            if otel_span:
                try:
                    from opentelemetry.trace import Status, StatusCode
                    if span.status == "ERROR":
                        otel_span.set_status(Status(StatusCode.ERROR, span.error))
                    otel_span.end()
                except Exception:
                    pass

            # End Sentry span
            if sentry_span:
                try:
                    sentry_span.finish()
                except Exception:
                    pass

            # Always log locally
            self._record_span(span)

    def capture_message(self, message: str, level: str = "info", extras: Optional[Dict[str, Any]] = None):
        """Capture a message to Sentry."""
        if self._sentry_initialized:
            try:
                import sentry_sdk
                with sentry_sdk.push_scope() as scope:
                    if extras:
                        for k, v in extras.items():
                            scope.set_extra(k, v)
                    sentry_sdk.capture_message(message, level=level)
            except Exception as e:
                logger.debug(f"Sentry capture error: {e}")

        # Always log locally
        logger.log(
            logging.INFO if level == "info" else logging.WARNING if level == "warning" else logging.ERROR,
            f"[{level.upper()}] {message}"
        )

    def _record_span(self, span: Span):
        """Record span to console and file."""
        span_dict = span.to_dict()

        # Console log (structured)
        log_line = json.dumps({
            "event": "span",
            **span_dict
        })
        logger.info(f"TRACE: {log_line}")

        # File log
        self._write_trace(span_dict)

        # Store in memory for analysis
        self._spans.append(span)

        # Keep only last 1000 spans in memory
        if len(self._spans) > 1000:
            self._spans = self._spans[-500:]

    def _write_trace(self, span_dict: dict):
        """Write span to daily trace file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        trace_file = TRACES_DIR / f"{date_str}.jsonl"

        try:
            with open(trace_file, "a") as f:
                f.write(json.dumps(span_dict) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write trace: {e}")

    def get_recent_spans(self, limit: int = 50) -> list[dict]:
        """Get recent spans for analysis."""
        return [s.to_dict() for s in self._spans[-limit:]]

    def get_stats(self) -> dict:
        """Get telemetry statistics."""
        if not self._spans:
            return {"total_spans": 0}

        durations = [s.duration_ms for s in self._spans if s.end_time]
        errors = [s for s in self._spans if s.status == "ERROR"]

        return {
            "total_spans": len(self._spans),
            "error_count": len(errors),
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "honeycomb_enabled": self._otel_tracer is not None,
            "sentry_enabled": self._sentry_initialized,
        }


# Global tracer instance
_tracer: Optional[RemoteMeTracer] = None


def get_tracer() -> RemoteMeTracer:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = RemoteMeTracer()
    return _tracer
