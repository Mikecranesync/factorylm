"""Digital twin diff engine — compares real PLC state vs Factory I/O simulation."""

import dataclasses
import logging

logger = logging.getLogger(__name__)

# Same tag mapping as sim/factoryio_bridge.py
COIL_MAP = {
    0: "motor_running", 1: "motor_stopped", 2: "fault_alarm",
    3: "conveyor_running", 4: "sensor_1_active", 5: "sensor_2_active",
    6: "e_stop_active",
}
REGISTER_MAP = {
    100: "motor_speed", 101: "motor_current", 102: "temperature",
    103: "pressure", 104: "conveyor_speed", 105: "error_code",
}

# Boolean tags where mismatch is always significant
CRITICAL_BOOL_TAGS = {"fault_alarm", "e_stop_active"}

ERROR_CODES = {
    0: "No error", 1: "Motor overload", 2: "Temperature high",
    3: "Conveyor jam", 4: "Sensor failure", 5: "Communication loss",
}


@dataclasses.dataclass
class TwinDiff:
    """Result of comparing real PLC state vs simulated state."""

    diverged: bool
    drift_score: float
    mismatches: list[dict]
    summary: str


class TwinReader:
    """Reads Factory I/O simulated tags via Modbus TCP."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._client = None

    def connect(self) -> bool:
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            logger.error("pymodbus not installed")
            return False

        self._client = ModbusTcpClient(self.host, port=self.port, timeout=3)
        if self._client.connect():
            logger.info("TwinReader connected to Factory I/O at %s:%d", self.host, self.port)
            return True
        logger.warning("TwinReader connection failed to %s:%d", self.host, self.port)
        self._client = None
        return False

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_socket_open()

    def read_tags(self) -> dict | None:
        """Read all mapped tags from Factory I/O. Returns None on error."""
        if not self.connected and not self.connect():
            return None

        try:
            coil_addrs = sorted(COIL_MAP.keys())
            coil_start = coil_addrs[0]
            coil_count = coil_addrs[-1] - coil_start + 1

            coils_result = self._client.read_coils(address=coil_start, count=coil_count)
            if coils_result.isError():
                logger.warning("TwinReader coil read error")
                self.disconnect()
                return None
            coil_bits = list(coils_result.bits[:coil_count])

            reg_addrs = sorted(REGISTER_MAP.keys())
            reg_start = reg_addrs[0]
            reg_count = reg_addrs[-1] - reg_start + 1

            regs_result = self._client.read_holding_registers(address=reg_start, count=reg_count)
            if regs_result.isError():
                logger.warning("TwinReader register read error")
                self.disconnect()
                return None
            reg_values = regs_result.registers

            tags = {}
            for addr, name in COIL_MAP.items():
                tags[name] = bool(coil_bits[addr - coil_start])

            for addr, name in REGISTER_MAP.items():
                raw = reg_values[addr - reg_start]
                if name == "motor_current":
                    tags[name] = round(raw / 10.0, 2)
                elif name == "temperature":
                    tags[name] = round(raw / 10.0, 1)
                else:
                    tags[name] = raw

            tags["error_message"] = ERROR_CODES.get(tags.get("error_code", 0), "Unknown")
            return tags

        except Exception as e:
            logger.warning("TwinReader read error: %s", e)
            self.disconnect()
            return None


class TwinComparator:
    """Computes diffs between real PLC tags and simulated tags."""

    def __init__(self, threshold: float = 0.15) -> None:
        self.threshold = threshold
        self._consecutive_divergences = 0

    def compare(self, real_tags: dict, sim_tags: dict) -> TwinDiff:
        """Compare real vs sim tags and return a TwinDiff."""
        mismatches = []
        total_checks = 0
        divergent_checks = 0

        # Compare boolean tags
        bool_tag_names = {v for v in COIL_MAP.values()}
        for name in bool_tag_names:
            real_val = real_tags.get(name)
            sim_val = sim_tags.get(name)
            if real_val is None or sim_val is None:
                continue
            total_checks += 1
            if bool(real_val) != bool(sim_val):
                divergent_checks += 1
                mismatches.append({
                    "tag": name,
                    "real": real_val,
                    "sim": sim_val,
                    "drift": 1.0,
                    "type": "bool",
                    "critical": name in CRITICAL_BOOL_TAGS,
                })

        # Compare numeric tags
        numeric_tag_names = {v for v in REGISTER_MAP.values() if v != "error_code"}
        for name in numeric_tag_names:
            real_val = real_tags.get(name)
            sim_val = sim_tags.get(name)
            if real_val is None or sim_val is None:
                continue
            total_checks += 1
            try:
                r = float(real_val)
                s = float(sim_val)
                drift = abs(r - s) / max(abs(s), 1.0)
                if drift > self.threshold:
                    divergent_checks += 1
                    mismatches.append({
                        "tag": name,
                        "real": real_val,
                        "sim": sim_val,
                        "drift": round(drift, 3),
                        "type": "numeric",
                        "critical": False,
                    })
            except (TypeError, ValueError):
                continue

        # Compare error_code specifically
        real_err = real_tags.get("error_code")
        sim_err = sim_tags.get("error_code")
        if real_err is not None and sim_err is not None:
            total_checks += 1
            if int(real_err) != int(sim_err):
                divergent_checks += 1
                mismatches.append({
                    "tag": "error_code",
                    "real": real_err,
                    "sim": sim_err,
                    "drift": 1.0,
                    "type": "enum",
                    "critical": True,
                })

        drift_score = divergent_checks / max(total_checks, 1)
        raw_diverged = len(mismatches) > 0

        # Debounce: require 2 consecutive divergent readings
        if raw_diverged:
            self._consecutive_divergences += 1
        else:
            self._consecutive_divergences = 0

        diverged = self._consecutive_divergences >= 2

        # Build summary
        if not mismatches:
            summary = "Real PLC and digital twin are in sync."
        else:
            parts = []
            for m in mismatches[:3]:
                tag = m["tag"]
                if m["type"] == "bool":
                    parts.append(f"{tag}: real={m['real']}, sim={m['sim']}")
                elif m["type"] == "numeric":
                    pct = int(m["drift"] * 100)
                    parts.append(f"{tag}: real={m['real']}, sim={m['sim']} ({pct}% drift)")
                else:
                    parts.append(f"{tag}: real={m['real']}, sim={m['sim']}")
            summary = "Divergence: " + "; ".join(parts)
            if len(mismatches) > 3:
                summary += f" (+{len(mismatches) - 3} more)"

        return TwinDiff(
            diverged=diverged,
            drift_score=round(drift_score, 3),
            mismatches=mismatches,
            summary=summary,
        )
