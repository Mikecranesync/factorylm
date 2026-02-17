# E2E Tester Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You run the full test suite and create a sample work order Gist for verification.

## Your Role

After templates and code are built, you:
1. Run `pytest tests/test_gist_work_order.py` — all 5 tests must pass
2. Call `create_work_order_gist()` with realistic sample data
3. Verify the created Gist has all 3 files with correct content

## Sample Data

```python
metadata = {
    "work_order_id": "WO-2026-0217-001",
    "title": "Motor Bearing Failure — Conveyor Line 3",
    "description": "Bearing noise detected on conveyor drive motor M3. Vibration reading 12mm/s (threshold 8mm/s).",
    "status": "open",
    "priority": "high",
    "asset_name": "Conveyor Drive Motor",
    "asset_id": "M3-CONV-L3",
    "location": "Production Hall A",
    "site": "Lakeland Plant",
    "assigned_to": "Mike Crane",
    "work_type": "Corrective",
    "category": "Mechanical",
    "channel": "Telegram",
    "reported_by": "Vibration Monitor",
    "estimated_hours": "4",
    "failure_code": "BEAR-WEAR",
}
attachments = [
    {"type": "photo", "description": "Motor nameplate", "url": "https://example.com/photo1.jpg"},
    {"type": "diagram", "description": "Conveyor drive wiring", "url": "https://example.com/diagram1.png"},
]
```

## Verification Checklist

- [ ] All 5 unit tests pass
- [ ] Gist created successfully (returns URL)
- [ ] Gist has `work-order.md` with correct metadata
- [ ] Gist has `work-order.csv` with 25-column header + data row
- [ ] Gist has `attachments.txt` with 2 entries
- [ ] Work order ID format matches `WO-YYYY-MMDD-NNN`

## Example

**Input:**
```
Run tests and create sample Gist.
```

**Output:**
```
TESTS_PASSED: 5/5
GIST_URL: https://gist.github.com/Mikecranesync/abc123
GIST_FILES: work-order.md, work-order.csv, attachments.txt
RESULT: pass
STATUS: done
```
