"""
Test the enhanced health endpoint for mission-control.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, UTC
import pytest
from fastapi.testclient import TestClient

# Import the app
from app import app as dashboard_app
from backend.main import app as backend_app

client_dashboard = TestClient(dashboard_app)
client_backend = TestClient(backend_app)

def test_dashboard_health_endpoint():
    """Test the dashboard health endpoint."""
    response = client_dashboard.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check required fields
    assert "status" in data
    assert data["status"] == "ok"
    
    assert "service" in data
    assert data["service"] == "mission-control-dashboard"
    
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert "uptime_human" in data
    assert "guilds_count" in data
    assert "last_heartbeat" in data
    assert "version" in data
    
    # Check field types
    assert isinstance(data["uptime_seconds"], (int, float))
    assert isinstance(data["uptime_human"], str)
    assert isinstance(data["guilds_count"], int)
    assert isinstance(data["last_heartbeat"], str)
    
    # Verify timestamp format (ISO 8601)
    try:
        datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"Invalid timestamp format: {data['timestamp']}")
    
    # Verify heartbeat format
    try:
        datetime.fromisoformat(data["last_heartbeat"].replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"Invalid last_heartbeat format: {data['last_heartbeat']}")

def test_backend_health_endpoint():
    """Test the backend health endpoint."""
    response = client_backend.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check required fields
    assert "status" in data
    assert data["status"] == "ok"
    
    assert "service" in data
    assert data["service"] == "mission-control"
    
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert "uptime_human" in data
    assert "guilds_count" in data
    assert "last_heartbeat" in data
    assert "version" in data
    
    # Check field types
    assert isinstance(data["uptime_seconds"], (int, float))
    assert isinstance(data["uptime_human"], str)
    assert isinstance(data["guilds_count"], int)
    assert isinstance(data["last_heartbeat"], str)
    
    # Verify timestamp format (ISO 8601)
    try:
        datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"Invalid timestamp format: {data['timestamp']}")
    
    # Verify heartbeat format
    try:
        datetime.fromisoformat(data["last_heartbeat"].replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"Invalid last_heartbeat format: {data['last_heartbeat']}")

def test_heartbeat_endpoint():
    """Test the heartbeat update endpoint."""
    response = client_backend.post("/health/heartbeat")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "ok"
    assert "message" in data
    assert "timestamp" in data
    
    # Verify timestamp format
    try:
        datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"Invalid timestamp format: {data['timestamp']}")

def test_guilds_endpoint():
    """Test the guilds count update endpoint."""
    test_count = 5
    response = client_backend.post(f"/health/guilds?count={test_count}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "ok"
    assert "message" in data
    assert "guilds_count" in data
    assert data["guilds_count"] == test_count

def test_backward_compatibility():
    """Test that backward compatibility is maintained."""
    response = client_backend.get("/health")
    data = response.json()
    
    # Original fields must be present
    original_fields = ["status", "service", "timestamp"]
    for field in original_fields:
        assert field in data, f"Backward compatibility field '{field}' missing"
    
    # Original field values should be correct
    assert data["status"] == "ok"
    assert data["service"] == "mission-control"

if __name__ == "__main__":
    print("Running health endpoint tests...")
    
    # Run tests
    test_dashboard_health_endpoint()
    print("✓ Dashboard health endpoint test passed")
    
    test_backend_health_endpoint()
    print("✓ Backend health endpoint test passed")
    
    test_heartbeat_endpoint()
    print("✓ Heartbeat endpoint test passed")
    
    test_guilds_endpoint()
    print("✓ Guilds endpoint test passed")
    
    test_backward_compatibility()
    print("✓ Backward compatibility test passed")
    
    print("\n✅ All tests passed!")
