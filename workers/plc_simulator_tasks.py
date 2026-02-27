"""
PLC Simulator Celery Tasks — auto-cycling conveyor sim for Cosmos demo.

Two tasks:
  simulator.tick   — Beat calls every 2s, drives physics + POSTs to Matrix API
  simulator.inject — Manual fault injection via `celery call`

Auto-cycle phases (~66s loop):
  idle(15s) → ramp_up(5s) → full_speed(20s) → e_stop(8s)
  → recovery(5s) → fault_jam(8s) → clear(5s) → idle...

Redis keys:
  sim:cycle_phase  — current phase name
  sim:cycle_start  — timestamp phase started (epoch float)
  sim:enabled      — auto-cycle on/off ("1"/"0", default "1")
"""

import logging
import os
import time

import redis

from sim.factoryio_bridge import post_to_matrix
from sim.plc_simulator import PLCSimulator
from workers.celery_app import app

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
MATRIX_URL = os.getenv("MATRIX_URL", "http://100.72.2.99:8001")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── Module-level singleton (lives in worker process memory) ─────────────────
_sim: PLCSimulator | None = None


def _get_sim() -> PLCSimulator:
    global _sim
    if _sim is None:
        _sim = PLCSimulator(node_id="sim-celery", db_path="sim/celery_tags.db")
        logger.info("PLCSimulator singleton created (node_id=sim-celery)")
    return _sim


# ── Redis client for cycle state ───────────────────────────────────────────
_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


# ── Auto-Cycle Phases ──────────────────────────────────────────────────────
PHASES = [
    ("idle",       15),
    ("ramp_up",     5),
    ("full_speed", 20),
    ("e_stop",      8),
    ("recovery",    5),
    ("fault_jam",   8),
    ("clear",       5),
]

PHASE_NAMES = [p[0] for p in PHASES]
PHASE_DURATIONS = {p[0]: p[1] for p in PHASES}


def _apply_phase(sim: PLCSimulator, phase: str, elapsed: float) -> None:
    """Apply phase-specific state to the simulator before tick()."""
    if phase == "idle":
        sim.motor_running = True
        sim.motor_speed = 60
        sim.conveyor_running = True
        sim.conveyor_speed = 50
        sim.e_stop = False
        sim.fault_alarm = False
        sim.error_code = 0

    elif phase == "ramp_up":
        progress = min(elapsed / PHASE_DURATIONS["ramp_up"], 1.0)
        sim.motor_running = True
        sim.motor_speed = int(60 + 20 * progress)
        sim.conveyor_speed = int(50 + 10 * progress)
        sim.e_stop = False
        sim.fault_alarm = False
        sim.error_code = 0

    elif phase == "full_speed":
        sim.motor_running = True
        sim.motor_speed = 80
        sim.conveyor_speed = 60
        sim.e_stop = False
        sim.fault_alarm = False
        sim.error_code = 0

    elif phase == "e_stop":
        sim.e_stop = True
        sim.motor_running = False
        sim.conveyor_running = False
        sim.fault_alarm = True
        sim.motor_speed = 0
        sim.conveyor_speed = 0
        sim.error_code = 0

    elif phase == "recovery":
        sim.e_stop = False
        sim.motor_running = True
        sim.conveyor_running = True
        sim.fault_alarm = False
        sim.error_code = 0
        progress = min(elapsed / PHASE_DURATIONS["recovery"], 1.0)
        sim.motor_speed = int(30 + 50 * progress)
        sim.conveyor_speed = int(20 + 40 * progress)

    elif phase == "fault_jam":
        sim.motor_running = True
        sim.conveyor_running = True
        sim.error_code = 3  # Conveyor jam — tick() handles speed=0, current spike
        sim.fault_alarm = True
        sim.e_stop = False

    elif phase == "clear":
        sim.error_code = 0
        sim.fault_alarm = False
        sim.motor_running = True
        sim.conveyor_running = True
        sim.motor_speed = 60
        sim.conveyor_speed = 50
        sim.e_stop = False


def _advance_cycle(r: redis.Redis) -> tuple[str, float]:
    """Check cycle state and advance phase if duration elapsed.

    Returns (current_phase, elapsed_in_phase).
    """
    enabled = r.get("sim:enabled")
    if enabled is not None and enabled == "0":
        phase = r.get("sim:cycle_phase") or "idle"
        start = float(r.get("sim:cycle_start") or time.time())
        return phase, time.time() - start

    phase = r.get("sim:cycle_phase")
    start_str = r.get("sim:cycle_start")
    now = time.time()

    if phase is None or start_str is None:
        # Initialize cycle
        r.set("sim:cycle_phase", "idle")
        r.set("sim:cycle_start", str(now))
        r.set("sim:enabled", "1")
        return "idle", 0.0

    start = float(start_str)
    elapsed = now - start
    duration = PHASE_DURATIONS.get(phase, 15)

    if elapsed >= duration:
        # Advance to next phase
        idx = PHASE_NAMES.index(phase) if phase in PHASE_NAMES else 0
        next_idx = (idx + 1) % len(PHASE_NAMES)
        next_phase = PHASE_NAMES[next_idx]
        r.set("sim:cycle_phase", next_phase)
        r.set("sim:cycle_start", str(now))
        logger.info("Phase transition: %s -> %s", phase, next_phase)
        return next_phase, 0.0

    return phase, elapsed


# ── Celery Tasks ───────────────────────────────────────────────────────────

@app.task(name="simulator.tick", bind=True, max_retries=0)
def tick(self):
    """Beat calls every 2s — drive auto-cycle physics, POST to Matrix API."""
    sim = _get_sim()
    r = _get_redis()

    # Advance auto-cycle
    phase, elapsed = _advance_cycle(r)

    # Apply phase state
    _apply_phase(sim, phase, elapsed)

    # Physics tick -> TagSnapshot
    snap = sim.tick()
    tags = snap.to_dict()

    # POST to Matrix API
    ok = post_to_matrix(MATRIX_URL, tags)

    return {
        "phase": phase,
        "elapsed": round(elapsed, 1),
        "posted": ok,
        "motor_speed": tags["motor_speed"],
        "temperature": tags["temperature"],
        "e_stop": tags["e_stop"],
        "fault_alarm": tags["fault_alarm"],
        "error_code": tags["error_code"],
    }


@app.task(name="simulator.inject", bind=True)
def inject(self, fault_name: str):
    """Manual fault injection. Pauses auto-cycle until 'resume' is sent.

    Usage:
      celery -A workers.celery_app call simulator.inject --args='["estop"]'
      celery -A workers.celery_app call simulator.inject --args='["jam"]'
      celery -A workers.celery_app call simulator.inject --args='["overload"]'
      celery -A workers.celery_app call simulator.inject --args='["clear"]'
      celery -A workers.celery_app call simulator.inject --args='["release"]'
      celery -A workers.celery_app call simulator.inject --args='["resume"]'
    """
    sim = _get_sim()
    r = _get_redis()

    # Pause auto-cycle for manual control
    r.set("sim:enabled", "0")
    logger.info("Auto-cycle paused for manual injection: %s", fault_name)

    # Special: "resume" re-enables auto-cycle
    if fault_name == "resume":
        r.set("sim:enabled", "1")
        r.set("sim:cycle_phase", "idle")
        r.set("sim:cycle_start", str(time.time()))
        return {"status": "Auto-cycle resumed", "phase": "idle"}

    result = sim.inject_fault(fault_name)
    logger.info("Manual inject: %s -> %s", fault_name, result)

    # Tick once to apply + post
    snap = sim.tick()
    post_to_matrix(MATRIX_URL, snap.to_dict())

    return {"status": result, "fault": fault_name, "auto_cycle": "paused"}
