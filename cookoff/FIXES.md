# FIXES.md — Cosmos Cookoff Training Record

Labeled training tuples from the 2026-03-05 sorting controller rebuild session.
Each entry captures: **(observation, state, root cause, fix)** for future Layer 0 codification.

---

## Fix 1: Controller crashes on startup — missing FactoryIOClient

| Field | Value |
|-------|-------|
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff setup |
| **Visual observation** | Factory I/O scene running but no sorting happening; Python traceback in terminal |
| **System state** | `sorting_controller.py` fails to import — `FactoryIOClient` undefined |
| **Root cause** | Original controller split across multiple files; monolithic rewrite needed single-file `FactoryIOClient` with Web API HTTP client |
| **Fix applied** | Rebuilt `sim/sorting_controller.py` from scratch — embedded `FactoryIOClient` class with httpx, id-based tag lookup, name→UUID mapping |
| **Files changed** | `sim/sorting_controller.py` |
| **Outcome** | verified working |

---

## Fix 2: Tag writes silently fail — wrong API contract

| Field | Value |
|-------|-------|
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff setup |
| **Visual observation** | Conveyor entry light stays OFF; boxes never move despite state machine showing RUNNING |
| **System state** | `write_tag()` returns 200 but Factory I/O ignores the values |
| **Root cause** | Factory I/O Web API expects `[{id, value}]` with UUIDs, not `{name: value}` dicts. Previous code used name-based writes. |
| **Fix applied** | Rewrote `FactoryIOClient.write_tag()` to use UUID lookup via `_name_to_id` map; PUT to `/api/tag/values` with `[{"id": uuid, "value": val}]` |
| **Files changed** | `sim/sorting_controller.py` |
| **Outcome** | verified working |

---

## Fix 3: Height sensors never trigger — input/output UUID collision

| Field | Value |
|-------|-------|
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff setup |
| **Visual observation** | Boxes reach sort zone but always go right (default); never sorted left for tall boxes |
| **System state** | `High sensor` and `Low sensor` always read `False` even when box is present |
| **Root cause** | Factory I/O has duplicate tag names for Input and Output. `_name_to_id` was storing the Output UUID, overwriting the Input UUID. Reads need the Input UUID. |
| **Fix applied** | Separated lookups: `_name_to_id` prefers Output (for writes), added `_input_name_to_id` for Input tags. `read_all_values()` returns Input values for sensor tags. |
| **Files changed** | `sim/sorting_controller.py` |
| **Outcome** | verified working |

---

## Fix 4: State machine stuck in SETTLING — settle counter never advances

| Field | Value |
|-------|-------|
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff setup |
| **Visual observation** | Box arrives at pallet sensor, conveyor stops, but nothing happens — box sits forever |
| **System state** | State = SETTLING, `settle_count` stays at 0 each scan |
| **Root cause** | `settle_count` was being reset to 0 at the top of `tick()` instead of being preserved across scans. Instance variable was shadowed by local variable. |
| **Fix applied** | Made `settle_count` a proper instance variable (`self._settle_count`) initialized in `__init__`, incremented in SETTLING state, reset on state transitions |
| **Files changed** | `sim/sorting_controller.py` |
| **Outcome** | verified working |

---

## Fix 5: Transfer arms don't activate — wrong tag names in write map

| Field | Value |
|-------|-------|
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff setup |
| **Visual observation** | Box sorted correctly (state goes to SORTING_LEFT) but no physical arm movement; box stays on conveyor |
| **System state** | State = SORTING_LEFT, but `Transf. left` Output tag stays False |
| **Root cause** | Tag name mismatch: code used `"Transfer left"` but Factory I/O scene uses `"Transf. left"` (abbreviated) |
| **Fix applied** | Updated all tag name references to match exact Factory I/O "Sorting by Height (Basic)" scene names: `"Transf. left"`, `"Transf. right"` |
| **Files changed** | `sim/sorting_controller.py` |
| **Outcome** | verified working |

---

## Fix 6: Watchdog timer fires during normal sort — too short timeout

| Field | Value |
|-------|-------|
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff setup |
| **Visual observation** | Box is mid-transfer on left arm, then suddenly arm retracts and state jumps to RUNNING |
| **System state** | `WATCHDOG_SCANS=50` fires before transfer completes (~2.5s at 20ms scan) |
| **Root cause** | Transfer arms in Factory I/O take 3-4 seconds to complete a full push. 50 scans at 20ms = 1s was too short. |
| **Fix applied** | Increased `WATCHDOG_SCANS` from 50 to 150 (3 seconds at 20ms scan rate), giving arms time to complete |
| **Files changed** | `sim/sorting_controller.py` |
| **Outcome** | verified working |

---

## Fix 7: Emergency stop doesn't halt — inverted logic

| Field | Value |
|-------|-------|
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff setup |
| **Visual observation** | Pressing E-stop button in Factory I/O has no effect; conveyor keeps running |
| **System state** | `Emergency stop` tag reads `True` when NOT pressed (NC contact), `False` when pressed |
| **Root cause** | E-stop in Factory I/O is normally-closed (NC). Code was checking `if emergency_stop == True` to trigger ESTOP, but True means safe. |
| **Fix applied** | Inverted the check: `if not tags["Emergency stop"]:` triggers ESTOP state. Added comment documenting NC logic. |
| **Files changed** | `sim/sorting_controller.py` |
| **Outcome** | verified working |

---

## Fix 8: Fault injector can't connect — missing force/release endpoints

| Field | Value |
|-------|-------|
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff setup |
| **Visual observation** | `fault_injector.py --fault jam` exits with "Cannot force tag" error |
| **System state** | `FactoryIOClient` had no `force_tag()` or `release_tag()` methods |
| **Root cause** | Original rebuild focused on read/write only. Force/release are separate Factory I/O endpoints: PUT `/api/tag/values-force` and PUT `/api/tag/values-release`. |
| **Fix applied** | Added `force_tag(name, value)` → PUT `[{id, value}]` to `/api/tag/values-force` and `release_tag(name)` → PUT `["id"]` to `/api/tag/values-release` |
| **Files changed** | `sim/sorting_controller.py` |
| **Outcome** | verified working |

---

## Fix 9: diagnosis_engine.py Windows encoding crash on R2 Unicode output

| Field | Value |
|-------|-------|
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff setup |
| **Visual observation** | Cosmos R2 returns diagnosis but script crashes with `UnicodeEncodeError` when printing to terminal |
| **System state** | Windows console (cp1252) can't encode em-dash, bullet, and other Unicode chars in R2's chain-of-thought |
| **Root cause** | Python defaults to system encoding (cp1252 on Windows) for stdout. R2 generates UTF-8 output with rich Unicode punctuation. |
| **Fix applied** | Added `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")` at top of `diagnosis_engine.py` |
| **Files changed** | `cookoff/diagnosis_engine.py` |
| **Outcome** | verified working |

---

## Session Summary

| Metric | Value |
|--------|-------|
| **Total fixes** | 9 |
| **Date** | 2026-03-05 |
| **Session** | Cosmos Cookoff — sorting controller rebuild |
| **Components** | sorting_controller (7), diagnosis_engine (1), fault_injector (1) |
| **All verified** | Yes |

### By Component

| Component | Fixes | IDs |
|-----------|-------|-----|
| `sim/sorting_controller.py` | 7 | 1, 2, 3, 4, 5, 6, 7 |
| `sim/fault_injector.py` | 1 | 8 |
| `cookoff/diagnosis_engine.py` | 1 | 9 |
