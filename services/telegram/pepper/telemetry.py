"""
PEPPER POTTS Telemetry

OpenTelemetry instrumentation with Honeycomb export.
Falls back to console/file logging if Honeycomb unavailable.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass, asdict

logger = logging.getLogger("pepper.telemetry")

# Trace storage for analysis
TRACES_DIR = Path(__file__).parent / "traces"
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


class PepperTracer:
    """
    Tracer for PEPPER POTTS bot.

    Exports to:
    1. Honeycomb (if API key available)
    2. Console (structured JSON)
    3. Local file (traces/{date}.jsonl)
    """

    def __init__(self):
        self.honeycomb_key = os.getenv("HONEYCOMB_API_KEY")
        self.service_name = "pepper-potts"
        self._otel_tracer = None
        self._spans: list[Span] = []

        # Initialize OTEL if available
        if self.honeycomb_key:
            self._init_otel()
        else:
            logger.info("Honeycomb API key not found, using local tracing")

    def _init_otel(self):
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
            logger.error(f"Failed to init OTEL: {e}")

    def _generate_id(self) -> str:
        """Generate a random trace/span ID."""
        import uuid
        return uuid.uuid4().hex[:16]

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        Create a tracing span.

        Usage:
            with tracer.span("handle_message", {"user.id": 123}) as span:
                span.set_attribute("llm.model", "llama-3.3-70b")
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
                        otel_span.set_attribute(k, v)
            except Exception as e:
                logger.debug(f"OTEL span error: {e}")

        try:
            yield span
            span.status = "OK"
        except Exception as e:
            span.set_status("ERROR", str(e))
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

            # Always log locally
            self._record_span(span)

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
        }

    def generate_report(self) -> str:
        """Generate a telemetry report."""
        stats = self.get_stats()
        recent = self.get_recent_spans(10)

        report = f"""
## 📊 PEPPER POTTS Telemetry Report

### Summary
- **Total Spans**: {stats['total_spans']}
- **Errors**: {stats['error_count']}
- **Avg Latency**: {stats['avg_duration_ms']:.2f}ms
- **Max Latency**: {stats['max_duration_ms']:.2f}ms
- **Honeycomb**: {'✅ Enabled' if stats['honeycomb_enabled'] else '❌ Local only'}

### Recent Traces
"""
        for span in recent:
            mode = span['attributes'].get('user.mode', 'UNKNOWN')
            action = span['attributes'].get('action.type', span['name'])
            report += f"- [{mode}] {action}: {span['duration_ms']:.0f}ms ({span['status']})\n"

        return report


# Global tracer instance
_tracer: Optional[PepperTracer] = None


def get_tracer() -> PepperTracer:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = PepperTracer()
    return _tracer
