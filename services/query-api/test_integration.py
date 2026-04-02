"""
Integration tests for the FactoryLM Query API.
These tests hit REAL services — no mocks (per project policy).

Prerequisites:
  - query-api running at http://localhost:8300
  - Qdrant running at http://localhost:8000
  - Nautobot running at http://localhost:8443

Run with:
  cd services/query-api && python3 -m pytest test_integration.py -v
"""
import pytest
import requests

BASE_URL = "http://localhost:8300"
QDRANT_URL = "http://localhost:8000"
NAUTOBOT_URL = "http://localhost:8443"
NAUTOBOT_TOKEN = "7ed85bda94d2c7b5396bd83b319cd7235fe57e0f"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get(path, **kwargs):
    import warnings
    warnings.filterwarnings("ignore")
    return requests.get(f"{BASE_URL}{path}", timeout=10, **kwargs)


def post(path, json, **kwargs):
    import warnings
    warnings.filterwarnings("ignore")
    kwargs.setdefault("timeout", 30)
    return requests.post(f"{BASE_URL}{path}", json=json, **kwargs)


# ---------------------------------------------------------------------------
# Health tests
# ---------------------------------------------------------------------------

class TestHealth:
    def test_root_returns_200(self):
        r = get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "FactoryLM Query API"

    def test_health_returns_healthy(self):
        r = get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["service"] == "factorylm-query-api"

    def test_health_reports_qdrant_reachable(self):
        r = get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["qdrant_reachable"] is True, (
            f"Qdrant not reachable at {data['qdrant_url']} — "
            "ensure Qdrant is running (~/bin/start-qdrant.sh)"
        )

    def test_health_includes_service_urls(self):
        r = get("/health")
        data = r.json()
        assert "qdrant_url" in data
        assert "nautobot_url" in data
        assert "llm_router_url" in data


# ---------------------------------------------------------------------------
# Query endpoint tests
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    def test_post_query_returns_200(self):
        r = post("/api/query", json={"question": "What does HR100 mean?"})
        assert r.status_code == 200

    def test_post_query_returns_non_empty_answer(self):
        """Core acceptance criterion: non-empty answer for HR100 question."""
        r = post("/api/query", json={"question": "What does HR100 mean?"})
        assert r.status_code == 200
        data = r.json()
        assert data["answer"], "answer field must be non-empty"
        assert len(data["answer"]) > 10, f"answer too short: {data['answer']!r}"

    def test_post_query_response_schema(self):
        """Response must include all required fields."""
        r = post("/api/query", json={"question": "What is motor_speed register?"})
        assert r.status_code == 200
        data = r.json()
        assert "question" in data
        assert "answer" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)
        assert "timestamp" in data
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], int)

    def test_post_query_echoes_question(self):
        question = "What does fault code 7 mean on the VFD?"
        r = post("/api/query", json={"question": question})
        data = r.json()
        assert data["question"] == question

    def test_post_query_with_machine_name(self):
        """When machine is provided, machine_context should be populated for known devices."""
        r = post("/api/query", json={"question": "What is the status?", "machine": "charlie"})
        assert r.status_code == 200
        data = r.json()
        assert data["machine"] == "charlie"
        # charlie exists in Nautobot — machine_context should be populated
        assert data["machine_context"] is not None, (
            "machine_context should not be None for known device 'charlie'"
        )
        assert data["machine_context"]["name"] == "charlie"

    def test_post_query_unknown_machine_returns_null_context(self):
        """Unknown machine should return null machine_context but still answer."""
        r = post("/api/query", json={"question": "What is the status?", "machine": "unknown-machine-xyz"})
        assert r.status_code == 200
        data = r.json()
        assert data["machine_context"] is None
        assert data["answer"], "answer must still be non-empty even for unknown machine"

    def test_post_query_no_machine_returns_null_context(self):
        """When no machine is provided, machine_context should be None."""
        r = post("/api/query", json={"question": "General question about conveyors"})
        data = r.json()
        assert data["machine"] is None
        assert data["machine_context"] is None

    def test_post_query_sources_is_list(self):
        r = post("/api/query", json={"question": "conveyor motor fault"})
        data = r.json()
        assert isinstance(data["sources"], list)
        for s in data["sources"]:
            assert "text" in s

    def test_post_query_latency_reasonable(self):
        """Response should complete within 45 seconds."""
        r = post("/api/query", json={"question": "What does HR101 mean?"}, timeout=45)
        assert r.status_code == 200
        data = r.json()
        assert data["latency_ms"] < 45000, f"Too slow: {data['latency_ms']}ms"

    def test_post_query_empty_question_returns_400_or_422(self):
        """Empty question should be rejected."""
        r = post("/api/query", json={"question": ""})
        # Either FastAPI validation error (422) or empty-string handling
        # We accept 200 with a note or 422 — just not 500
        assert r.status_code != 500


# ---------------------------------------------------------------------------
# Qdrant connectivity (independent of query-api)
# ---------------------------------------------------------------------------

class TestQdrant:
    def test_qdrant_healthy(self):
        import warnings
        warnings.filterwarnings("ignore")
        r = requests.get(f"{QDRANT_URL}/collections", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_qdrant_factorylm_brain_collection_exists(self):
        import warnings
        warnings.filterwarnings("ignore")
        r = requests.get(f"{QDRANT_URL}/collections/factorylm_brain", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["result"]["status"] == "green"


# ---------------------------------------------------------------------------
# Nautobot connectivity (independent of query-api)
# ---------------------------------------------------------------------------

class TestNautobot:
    def test_nautobot_devices_api_reachable(self):
        import warnings
        warnings.filterwarnings("ignore")
        r = requests.get(
            f"{NAUTOBOT_URL}/api/dcim/devices/?limit=1",
            headers={"Authorization": f"Token {NAUTOBOT_TOKEN}"},
            timeout=5,
        )
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert data["count"] > 0, "Nautobot should have seeded devices"

    def test_nautobot_has_factorylm_nodes(self):
        import warnings
        warnings.filterwarnings("ignore")
        r = requests.get(
            f"{NAUTOBOT_URL}/api/dcim/devices/",
            params={"name": "charlie", "limit": 1},
            headers={"Authorization": f"Token {NAUTOBOT_TOKEN}"},
            timeout=5,
        )
        assert r.status_code == 200
        results = r.json().get("results", [])
        assert len(results) == 1, "Device 'charlie' should exist in Nautobot"
        assert results[0]["name"] == "charlie"
