"""
PLC Simulator — publishes realistic conveyor/motor tags for FactoryLM demos.

Simulates an Allen-Bradley Micro 820 controlling a sorting station conveyor.
Tags are stored in a local SQLite database and printed to stdout as JSON.

Usage:
    python sim/plc_simulator.py                    # Normal operation
    python sim/plc_simulator.py --interval 200     # 200ms between reads
    python sim/plc_simulator.py --fault jam         # Start with a jam fault
    python sim/plc_simulator.py --duration 60       # Run for 60 seconds

Fault injection (interactive):
    While running, type a fault name and press Enter:
        jam          — Conveyor jam (error_code=3)
        overload     — Motor overload (error_code=1)
        overheat     — Temperature high (error_code=2)
        sensor       — Sensor failure (error_code=4)
        clear        — Clear all faults
        estop        — Emergency stop
        release      — Release e-stop
"""

import argparse
import asyncio
import dataclasses
import datetime
import json
import logging
import random
import sqlite3
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Error codes matching services/plc-modbus/src/factorylm_plc/models.py
ERROR_CODES = {
    0: "No error",
    1: "Motor overload",
    2: "Temperature high",
    3: "Conveyor jam",
    4: "Sensor failure",
    5: "Communication loss",
}

FAULT_MAP = {
    "jam": 3,
    "overload": 1,
    "overheat": 2,
    "sensor": 4,
    "comms": 5,
}


@dataclasses.dataclass
class TagSnapshot:
    """A single point-in-time reading of all PLC tags."""

    timestamp: str
    node_id: str
    motor_running: bool
    motor_speed: int
    motor_current: float
    temperature: float
    pressure: int
    conveyor_running: bool
    conveyor_speed: int
    sensor_1: bool
    sensor_2: bool
    fault_alarm: bool
    e_stop: bool
    error_code: int
    error_message: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class PLCSimulator:
    """Simulates a Micro 820 PLC with realistic conveyor behaviour."""

    def __init__(
        self,
        node_id: str = "sim-micro820",
        interval_ms: int = 500,
        db_path: str | None = None,
    ) -> None:
        self.node_id = node_id
        self.interval_ms = interval_ms
        self._running = False

        # State
        self.motor_running = True
        self.motor_speed = 60
        self.motor_current = 3.0
        self.temperature = 25.0
        self.pressure = 100
        self.conveyor_running = True
        self.conveyor_speed = 50
        self.sensor_1 = False
        self.sensor_2 = False
        self.fault_alarm = False
        self.e_stop = False
        self.error_code = 0

        # SQLite for local tag storage
        self._db_path = Path(db_path) if db_path else Path("sim/tags.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create the tags table if it doesn't exist."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tag_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                node_id TEXT NOT NULL,
                motor_running INTEGER,
                motor_speed INTEGER,
                motor_current REAL,
                temperature REAL,
                pressure INTEGER,
                conveyor_running INTEGER,
                conveyor_speed INTEGER,
                sensor_1 INTEGER,
                sensor_2 INTEGER,
                fault_alarm INTEGER,
                e_stop INTEGER,
                error_code INTEGER,
                error_message TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _store_snapshot(self, snap: TagSnapshot) -> None:
        """Write a snapshot to SQLite."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            """INSERT INTO tag_snapshots
               (timestamp, node_id, motor_running, motor_speed, motor_current,
                temperature, pressure, conveyor_running, conveyor_speed,
                sensor_1, sensor_2, fault_alarm, e_stop, error_code, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snap.timestamp, snap.node_id,
                int(snap.motor_running), snap.motor_speed, snap.motor_current,
                snap.temperature, snap.pressure,
                int(snap.conveyor_running), snap.conveyor_speed,
                int(snap.sensor_1), int(snap.sensor_2),
                int(snap.fault_alarm), int(snap.e_stop),
                snap.error_code, snap.error_message,
            ),
        )
        conn.commit()
        conn.close()

    def tick(self) -> TagSnapshot:
        """Advance simulation by one step and return the current tag snapshot."""
        # Normal operation: motor current fluctuates with speed
        if self.motor_running and not self.e_stop:
            base_current = self.motor_speed * 0.05
            self.motor_current = round(base_current + random.uniform(-0.3, 0.3), 2)
        else:
            self.motor_current = 0.0

        # Temperature: slowly rises when running, cools when stopped
        if self.motor_running and not self.e_stop:
            if self.temperature < 45.0:
                self.temperature = round(self.temperature + random.uniform(0.05, 0.15), 1)
        else:
            if self.temperature > 22.0:
                self.temperature = round(self.temperature - random.uniform(0.1, 0.3), 1)

        # Sensors: toggle randomly to simulate parts on conveyor
        if self.conveyor_running and not self.e_stop:
            if random.random() < 0.15:
                self.sensor_1 = not self.sensor_1
            if random.random() < 0.10:
                self.sensor_2 = not self.sensor_2
        else:
            self.sensor_1 = False
            self.sensor_2 = False

        # Pressure: mild fluctuation
        self.pressure = max(90, min(110, self.pressure + random.randint(-1, 1)))

        # Fault effects
        if self.error_code == 1:  # Motor overload
            self.motor_current = round(self.motor_speed * 0.12 + random.uniform(0, 1.0), 2)
        elif self.error_code == 2:  # Temperature high
            self.temperature = round(min(95.0, self.temperature + random.uniform(0.5, 1.5)), 1)
        elif self.error_code == 3:  # Conveyor jam
            self.conveyor_speed = 0
            self.sensor_1 = True  # Part stuck
            self.motor_current = round(self.motor_speed * 0.10 + random.uniform(0, 0.5), 2)

        snap = TagSnapshot(
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            node_id=self.node_id,
            motor_running=self.motor_running,
            motor_speed=self.motor_speed,
            motor_current=self.motor_current,
            temperature=self.temperature,
            pressure=self.pressure,
            conveyor_running=self.conveyor_running,
            conveyor_speed=self.conveyor_speed if self.error_code != 3 else 0,
            sensor_1=self.sensor_1,
            sensor_2=self.sensor_2,
            fault_alarm=self.fault_alarm,
            e_stop=self.e_stop,
            error_code=self.error_code,
            error_message=ERROR_CODES.get(self.error_code, f"Unknown error {self.error_code}"),
        )
        self._store_snapshot(snap)
        return snap

    def inject_fault(self, fault_name: str) -> str:
        """Inject a named fault. Returns a status message."""
        if fault_name == "clear":
            self.error_code = 0
            self.fault_alarm = False
            self.conveyor_speed = 50
            return "Faults cleared"
        elif fault_name == "estop":
            self.e_stop = True
            self.motor_running = False
            self.conveyor_running = False
            self.fault_alarm = True
            return "E-STOP activated"
        elif fault_name == "release":
            self.e_stop = False
            self.motor_running = True
            self.conveyor_running = True
            self.motor_speed = 60
            self.conveyor_speed = 50
            self.fault_alarm = False
            self.error_code = 0
            return "E-STOP released, system restarted"
        elif fault_name in FAULT_MAP:
            self.error_code = FAULT_MAP[fault_name]
            self.fault_alarm = True
            msg = ERROR_CODES.get(self.error_code, fault_name)
            return f"Fault injected: {msg} (error_code={self.error_code})"
        else:
            return f"Unknown fault: {fault_name}. Options: {', '.join(list(FAULT_MAP) + ['clear', 'estop', 'release'])}"


async def _stdin_reader(sim: PLCSimulator) -> None:
    """Read fault commands from stdin in a non-blocking loop."""
    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        cmd = line.strip().lower()
        if cmd:
            result = sim.inject_fault(cmd)
            logger.info(">>> %s", result)


async def run_simulator(
    interval_ms: int = 500,
    duration: int | None = None,
    initial_fault: str | None = None,
    db_path: str | None = None,
) -> None:
    """Run the PLC simulator loop."""
    sim = PLCSimulator(interval_ms=interval_ms, db_path=db_path)

    if initial_fault:
        result = sim.inject_fault(initial_fault)
        logger.info("Initial fault: %s", result)

    logger.info(
        "PLC Simulator started — node=%s interval=%dms db=%s",
        sim.node_id, interval_ms, sim._db_path,
    )
    logger.info("Type a fault command and press Enter: jam, overload, overheat, sensor, clear, estop, release")

    # Start stdin reader for interactive fault injection
    stdin_task = asyncio.create_task(_stdin_reader(sim))

    start = time.monotonic()
    try:
        while True:
            snap = sim.tick()
            print(snap.to_json(), flush=True)

            if duration and (time.monotonic() - start) >= duration:
                logger.info("Duration reached (%ds), stopping.", duration)
                break

            await asyncio.sleep(interval_ms / 1000.0)
    except asyncio.CancelledError:
        pass
    finally:
        stdin_task.cancel()
        logger.info("Simulator stopped. %s contains tag history.", sim._db_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="FactoryLM PLC Simulator")
    parser.add_argument("--interval", type=int, default=500, help="Interval between reads in ms (default: 500)")
    parser.add_argument("--duration", type=int, default=None, help="Run for N seconds then stop (default: forever)")
    parser.add_argument("--fault", type=str, default=None, choices=list(FAULT_MAP) + ["estop"], help="Start with a fault")
    parser.add_argument("--db", type=str, default=None, help="Path to SQLite database (default: sim/tags.db)")
    args = parser.parse_args()

    try:
        asyncio.run(run_simulator(
            interval_ms=args.interval,
            duration=args.duration,
            initial_fault=args.fault,
            db_path=args.db,
        ))
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")


if __name__ == "__main__":
    main()
