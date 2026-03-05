"""
observability.metrics — Write metrics to InfluxDB (or log-only fallback).

Usage::

    from observability.metrics import write_metric

    write_metric(
        measurement="edge_gateway_health",
        tags={"status": "healthy", "component": "edge_gateway"},
        fields={"uptime": 1, "latency_ms": 12.3},
    )

If ``influxdb-client`` is installed *and* ``INFLUXDB_URL`` is set the points
are written to InfluxDB.  Otherwise the call is a silent no-op (DEBUG log).
"""

import logging
import os

log = logging.getLogger("factorylm.metrics")

# ---------------------------------------------------------------------------
# Lazy InfluxDB client
# ---------------------------------------------------------------------------

_influx_write_api = None
_influx_init_done = False

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "factorylm")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensors")


def _get_write_api():
    """Return an InfluxDB write API, or None if unavailable."""
    global _influx_write_api, _influx_init_done
    if _influx_init_done:
        return _influx_write_api
    _influx_init_done = True

    if not INFLUXDB_URL:
        log.debug("INFLUXDB_URL not set — metrics will only be logged")
        return None

    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS

        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        _influx_write_api = client.write_api(write_options=SYNCHRONOUS)
        log.info("InfluxDB metrics enabled → %s", INFLUXDB_URL)
        return _influx_write_api
    except ImportError:
        log.debug("influxdb-client not installed — metrics will only be logged")
    except Exception as exc:
        log.warning("InfluxDB init failed (%s) — metrics will only be logged", exc)

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_metric(measurement: str, tags: dict | None = None, fields: dict | None = None):
    """Write a metric point to InfluxDB if available, otherwise log at DEBUG level."""
    tags = tags or {}
    fields = fields or {}

    log.debug("METRIC %s tags=%s fields=%s", measurement, tags, fields)

    api = _get_write_api()
    if api is None:
        return

    try:
        from influxdb_client import Point

        point = Point(measurement)
        for k, v in tags.items():
            point = point.tag(k, str(v))
        for k, v in fields.items():
            point = point.field(k, v)

        api.write(bucket=INFLUXDB_BUCKET, record=point)
    except Exception as exc:
        log.warning("Failed to write metric %s: %s", measurement, exc)


def write_celery_task(task_name: str, status: str = "success", duration_ms: float = 0):
    """Convenience: record a Celery task execution metric."""
    write_metric(
        measurement="celery_task",
        tags={"task": task_name, "status": status},
        fields={"duration_ms": duration_ms, "count": 1},
    )


def write_llm_call(provider: str, model: str, tokens: int = 0, latency_ms: float = 0):
    """Convenience: record an LLM API call metric."""
    write_metric(
        measurement="llm_call",
        tags={"provider": provider, "model": model},
        fields={"tokens": tokens, "latency_ms": latency_ms, "count": 1},
    )
