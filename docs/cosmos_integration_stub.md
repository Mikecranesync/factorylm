# Cosmos Reason 2 Integration — Stub Guide

**Last Updated:** 2026-02-13  
**Status:** Stub — ready for real API swap

---

## Current State

The Cosmos integration is fully wired end-to-end but uses **stub responses** instead of calling the real NVIDIA Cosmos Reason 2 API. This means:

- ✅ `cosmos/client.py` — `CosmosClient.analyze_incident()` returns realistic hard-coded responses per fault type
- ✅ `cosmos/agent.py` — `CosmosAgent` watches for faults and stores `CosmosInsight` results
- ✅ `config/cosmos.yaml` — Configuration for model, triggers, video, and storage
- ✅ `sim/plc_simulator.py` — Generates realistic tag data with injectable faults
- ❌ Real Cosmos Reason 2 API calls — NOT YET IMPLEMENTED

---

## Where to Plug In the Real API

### File: `cosmos/client.py`

The `analyze_incident()` method has a clear TODO marker. Replace the stub with:

```python
# In cosmos/client.py, inside analyze_incident():

import httpx  # or requests

response = httpx.post(
    f"{self.api_base_url}/v1/analyze",
    headers={
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": self.model,
        "images": images or [],
        "tags": tags,
        "video_url": video_url,
        "context": context,
    },
    timeout=30.0,
)
response.raise_for_status()
data = response.json()

return CosmosInsight(
    incident_id=incident_id,
    node_id=node_id,
    timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    summary=data["summary"],
    root_cause=data["root_cause"],
    confidence=data["confidence"],
    reasoning=data["reasoning"],
    suggested_checks=data.get("suggested_checks", []),
    video_url=video_url,
    cosmos_model=self.model,
)
```

### Config: `config/cosmos.yaml`

Set `enabled: true` and configure the real API URL:

```yaml
cosmos:
  enabled: true
  model: "nvidia/cosmos-reason2"
  api_base_url: "https://build.nvidia.com/api/v1"  # or your endpoint
```

### Secret: `NVIDIA_COSMOS_API_KEY`

Set via Doppler or environment variable:

```bash
# Via Doppler
doppler secrets set NVIDIA_COSMOS_API_KEY "nvapi-your-key" --project factorylm-core --config dev

# Or directly
export NVIDIA_COSMOS_API_KEY="nvapi-your-key"
```

---

## API Access Options

| Option | URL | Notes |
|--------|-----|-------|
| NVIDIA Build | build.nvidia.com | Free trial, API playground |
| AWS Marketplace | aws.amazon.com/marketplace | Pay-per-use, production-grade |
| Self-hosted | Your GPU server | Air-gapped option |

---

## Testing the Swap

After plugging in the real API:

```bash
# 1. Run tests (should still pass — tests use stubs)
pytest tests/unit/test_cosmos_agent.py -v

# 2. Manual integration test
python -c "
from cosmos.client import CosmosClient
client = CosmosClient()
print('Available:', client.is_available())
insight = client.analyze_incident(
    incident_id='TEST-001',
    node_id='sim-micro820',
    tags={'error_code': 3, 'motor_current': 8.5, 'conveyor_speed': 0},
)
print('Summary:', insight.summary)
print('Root cause:', insight.root_cause)
print('Confidence:', insight.confidence)
"
```
