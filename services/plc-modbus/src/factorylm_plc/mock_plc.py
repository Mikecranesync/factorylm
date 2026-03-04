"""
Mock PLC — simulates a Micro 820 + VFD + conveyor ("From A to B" scene).

Coil map matches plc_connection.py COIL_NAMES exactly:
  0-6   program coils   (Conveyor, Emitter, SensorStart, SensorEnd, RunCommand, …)
  7-14  physical inputs  (DI_00-DI_07: selector switch, E-stop, pushbutton)
  15-17 physical outputs (DO_00, DO_01, DO_03: indicator LEDs)

Register map (100-105):
  100  ItemCount       — items that reached SensorEnd
  101  ConveyorHz      — VFD frequency 0-60 Hz
  102  MotorCurrentX10 — motor current in tenths of amp (e.g. 45 = 4.5 A)
  103  MotorTempX10    — motor temperature in tenths of °C (e.g. 312 = 31.2 °C)
  104  VFDStatus       — 0=idle, 1=running, 2=fault
  105  ErrorCode       — 0=none, 1=overload, 2=overheat, 3=sensor-fail, 4=jam, 7=e-stop
"""

import random
from datetime import datetime
from typing import List, Dict, Any

from .base import BasePLCClient
from .models import FactoryState


class MockPLC(BasePLCClient):
    """Simulated Micro 820 + VFD for the 'From A to B' Factory I/O scene."""

    # ── Coil addresses (match plc_connection.py exactly) ──────────────
    # Program coils
    COIL_CONVEYOR = 0       # belt motor output
    COIL_EMITTER = 1        # item spawner output
    COIL_SENSOR_START = 2   # entry sensor (Factory I/O → PLC)
    COIL_SENSOR_END = 3     # exit sensor  (Factory I/O → PLC)
    COIL_RUN_COMMAND = 4    # remote start/stop
    # Physical inputs
    COIL_DI_00 = 7          # 3-pos switch CENTER
    COIL_DI_01 = 8          # E-stop NO contact
    COIL_DI_02 = 9          # E-stop NC contact (True = released)
    COIL_DI_03 = 10         # 3-pos switch RIGHT
    COIL_DI_04 = 11         # Left pushbutton
    # Physical outputs
    COIL_DO_00 = 15         # switch indicator LED
    COIL_DO_01 = 16         # E-stop indicator LED
    COIL_DO_03 = 17         # auxiliary output

    # ── Register addresses ────────────────────────────────────────────
    REG_ITEM_COUNT = 100
    REG_CONVEYOR_HZ = 101
    REG_MOTOR_CURRENT_X10 = 102
    REG_MOTOR_TEMP_X10 = 103
    REG_VFD_STATUS = 104
    REG_ERROR_CODE = 105

    def __init__(self, initial_state: Dict[str, Any] | None = None):
        self._connected = False
        self._tick = 0          # monotonic sim tick (incremented each read)
        self._item_in_transit = False
        self._item_progress = 0  # 0-5, when it hits 5 the item reaches SensorEnd

        # 18 coils (0-17), all False except E-stop NC (released = True)
        self._coils: Dict[int, bool] = {i: False for i in range(18)}
        self._coils[self.COIL_DI_02] = True   # NC contact: True when e-stop released
        self._coils[self.COIL_DI_00] = True    # switch starts at CENTER
        self._coils[self.COIL_DO_00] = True    # switch indicator reflects CENTER

        # 6 registers
        self._registers: Dict[int, int] = {
            self.REG_ITEM_COUNT: 0,
            self.REG_CONVEYOR_HZ: 0,
            self.REG_MOTOR_CURRENT_X10: 0,
            self.REG_MOTOR_TEMP_X10: 250,   # 25.0 °C ambient
            self.REG_VFD_STATUS: 0,          # idle
            self.REG_ERROR_CODE: 0,
        }

        if initial_state:
            self._apply_initial_state(initial_state)

        self.scene_name = "from_a_to_b"

    # ── BasePLCClient interface ───────────────────────────────────────

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise ConnectionError("MockPLC is not connected")

    def read_coils(self, address: int, count: int) -> List[bool]:
        self._ensure_connected()
        self._simulate()
        return [self._coils.get(address + i, False) for i in range(count)]

    def read_holding_registers(self, address: int, count: int) -> List[int]:
        self._ensure_connected()
        self._simulate()
        return [self._registers.get(address + i, 0) for i in range(count)]

    def write_coil(self, address: int, value: bool) -> bool:
        self._ensure_connected()
        self._coils[address] = value

        # RunCommand controls Conveyor + Emitter
        if address == self.COIL_RUN_COMMAND:
            if value:
                self._coils[self.COIL_CONVEYOR] = True
                self._coils[self.COIL_EMITTER] = True
                self._registers[self.REG_CONVEYOR_HZ] = 30  # default 30 Hz
                self._registers[self.REG_VFD_STATUS] = 1
            else:
                self._coils[self.COIL_CONVEYOR] = False
                self._coils[self.COIL_EMITTER] = False
                self._registers[self.REG_CONVEYOR_HZ] = 0
                self._registers[self.REG_VFD_STATUS] = 0

        return True

    def write_register(self, address: int, value: int) -> bool:
        self._ensure_connected()
        self._registers[address] = value
        return True

    # ── Simulation engine ─────────────────────────────────────────────

    def _simulate(self) -> None:
        """Advance one tick of conveyor + VFD physics."""
        self._tick += 1
        conveyor_on = self._coils[self.COIL_CONVEYOR]
        estop = self._coils[self.COIL_DI_01] and not self._coils[self.COIL_DI_02]
        hz = self._registers[self.REG_CONVEYOR_HZ]
        temp = self._registers[self.REG_MOTOR_TEMP_X10]

        # ── E-stop overrides everything ───────────────────────────────
        if estop:
            self._coils[self.COIL_CONVEYOR] = False
            self._coils[self.COIL_EMITTER] = False
            self._registers[self.REG_CONVEYOR_HZ] = 0
            self._registers[self.REG_MOTOR_CURRENT_X10] = 0
            self._registers[self.REG_VFD_STATUS] = 2  # fault
            self._registers[self.REG_ERROR_CODE] = 7
            self._coils[self.COIL_DO_01] = True  # e-stop LED on
            return

        self._coils[self.COIL_DO_01] = False  # e-stop LED off

        # ── VFD physics ───────────────────────────────────────────────
        if conveyor_on and hz > 0:
            # Current = (hz/60) * 8.0 A baseline + noise, stored as tenths
            base = int((hz / 60.0) * 80)
            noise = random.randint(-5, 5)
            self._registers[self.REG_MOTOR_CURRENT_X10] = max(0, base + noise)

            # Temperature rises when running (max 75.0 °C = 750)
            if temp < 750:
                self._registers[self.REG_MOTOR_TEMP_X10] = min(750, temp + random.randint(1, 3))

            self._registers[self.REG_VFD_STATUS] = 1  # running
        else:
            # Cool down toward ambient
            self._registers[self.REG_MOTOR_CURRENT_X10] = 0
            if temp > 250:
                self._registers[self.REG_MOTOR_TEMP_X10] = max(250, temp - random.randint(2, 6))
            self._registers[self.REG_VFD_STATUS] = 0 if self._registers[self.REG_ERROR_CODE] == 0 else 2

        # ── Item flow (conveyor moving items from A to B) ─────────────
        if conveyor_on:
            if not self._item_in_transit:
                # New item appears at entry sensor (20% chance per tick)
                if random.random() < 0.20:
                    self._item_in_transit = True
                    self._item_progress = 0
                    self._coils[self.COIL_SENSOR_START] = True
                    self._coils[self.COIL_SENSOR_END] = False
            else:
                # Item progresses along conveyor
                self._item_progress += 1
                # Item leaves entry sensor after 2 ticks
                if self._item_progress >= 2:
                    self._coils[self.COIL_SENSOR_START] = False
                # Item reaches exit sensor at 5 ticks
                if self._item_progress >= 5:
                    self._coils[self.COIL_SENSOR_END] = True
                    self._registers[self.REG_ITEM_COUNT] += 1
                    self._item_in_transit = False
                    self._item_progress = 0
        else:
            self._coils[self.COIL_SENSOR_START] = False
            self._coils[self.COIL_SENSOR_END] = False

        # ── Physical output LEDs ──────────────────────────────────────
        # Switch indicator: ON when CENTER or RIGHT
        self._coils[self.COIL_DO_00] = (
            self._coils[self.COIL_DI_00] or self._coils[self.COIL_DI_03]
        )

    # ── Convenience methods for fault injection ───────────────────────

    def start_conveyor(self, hz: int = 30) -> None:
        """Start the conveyor at given frequency."""
        self.write_coil(self.COIL_RUN_COMMAND, True)
        self._registers[self.REG_CONVEYOR_HZ] = min(60, max(0, hz))

    def stop_conveyor(self) -> None:
        """Stop the conveyor."""
        self.write_coil(self.COIL_RUN_COMMAND, False)

    def trigger_estop(self) -> None:
        """Press the E-stop button."""
        self._coils[self.COIL_DI_01] = True   # NO closes
        self._coils[self.COIL_DI_02] = False   # NC opens

    def release_estop(self) -> None:
        """Release the E-stop button."""
        self._coils[self.COIL_DI_01] = False
        self._coils[self.COIL_DI_02] = True
        self._registers[self.REG_ERROR_CODE] = 0

    def inject_overload(self) -> None:
        """Simulate motor overload (current spike)."""
        self._registers[self.REG_MOTOR_CURRENT_X10] = 95  # 9.5 A
        self._registers[self.REG_ERROR_CODE] = 1
        self._registers[self.REG_VFD_STATUS] = 2

    def inject_overheat(self) -> None:
        """Simulate motor overheat."""
        self._registers[self.REG_MOTOR_TEMP_X10] = 850  # 85.0 °C
        self._registers[self.REG_ERROR_CODE] = 2
        self._registers[self.REG_VFD_STATUS] = 2

    def inject_sensor_failure(self) -> None:
        """Simulate both sensors stuck off."""
        self._coils[self.COIL_SENSOR_START] = False
        self._coils[self.COIL_SENSOR_END] = False
        self._item_in_transit = False
        self._registers[self.REG_ERROR_CODE] = 3

    def inject_jam(self) -> None:
        """Simulate item jammed on entry sensor."""
        self._coils[self.COIL_SENSOR_START] = True
        self._coils[self.COIL_SENSOR_END] = False
        self._item_in_transit = True
        self._item_progress = 0  # stuck
        self._registers[self.REG_ERROR_CODE] = 4

    def clear_faults(self) -> None:
        """Reset all fault conditions."""
        self._registers[self.REG_ERROR_CODE] = 0
        self._registers[self.REG_VFD_STATUS] = 1 if self._coils[self.COIL_CONVEYOR] else 0

    # ── Legacy interface (used by read_state / FactoryState) ──────────

    def read_state(self) -> FactoryState:
        """Read complete factory state (legacy interface for FactoryState model)."""
        self._ensure_connected()
        self._simulate()

        # Read raw data without triggering extra _simulate() calls
        coils = [self._coils.get(i, False) for i in range(18)]
        regs = [self._registers.get(100 + i, 0) for i in range(6)]

        return FactoryState(
            motor_running=coils[self.COIL_CONVEYOR],
            motor_speed=regs[1],                    # ConveyorHz
            motor_current=regs[2] / 10.0,           # tenths → amps
            temperature=regs[3] / 10.0,             # tenths → °C
            pressure=0,                             # not simulated in this scene
            fault_active=regs[5] > 0,               # any error code
            conveyor_speed=regs[1],                 # same as motor speed
            conveyor_running=coils[self.COIL_CONVEYOR],
            sensor_1_active=coils[self.COIL_SENSOR_START],
            sensor_2_active=coils[self.COIL_SENSOR_END],
            e_stop_active=coils[self.COIL_DI_01] and not coils[self.COIL_DI_02],
            error_code=regs[5],
            timestamp=datetime.now(),
            scene_name=self.scene_name,
        )

    def _apply_initial_state(self, state: Dict[str, Any]) -> None:
        """Apply initial state overrides."""
        coil_map = {
            "conveyor": self.COIL_CONVEYOR,
            "emitter": self.COIL_EMITTER,
            "sensor_start": self.COIL_SENSOR_START,
            "sensor_end": self.COIL_SENSOR_END,
            "run_command": self.COIL_RUN_COMMAND,
            "e_stop_no": self.COIL_DI_01,
            "e_stop_nc": self.COIL_DI_02,
        }
        register_map = {
            "item_count": self.REG_ITEM_COUNT,
            "conveyor_hz": self.REG_CONVEYOR_HZ,
            "motor_current": self.REG_MOTOR_CURRENT_X10,
            "motor_temp": self.REG_MOTOR_TEMP_X10,
            "error_code": self.REG_ERROR_CODE,
        }
        for key, value in state.items():
            if key in coil_map:
                self._coils[coil_map[key]] = bool(value)
            elif key in register_map:
                self._registers[register_map[key]] = int(value)

    # Keep old helper names working
    def start_motor(self, speed: int = 30) -> bool:
        self.start_conveyor(speed)
        return True

    def stop_motor(self) -> bool:
        self.stop_conveyor()
        return True

    def trigger_error(self, error_code: int) -> None:
        if error_code > 0:
            self._registers[self.REG_ERROR_CODE] = error_code
            self._registers[self.REG_VFD_STATUS] = 2
        else:
            self.clear_faults()

    def clear_error(self) -> None:
        self.clear_faults()
