"""Vision-based belt tachometer — tracks orange tape to compute RPM and detect faults.

Uses HSV color masking to find bright orange tape across the belt width,
tracks crossings of a virtual centerline to compute RPM, and buffers
raw frames for Cosmos video diagnosis on fault.

All tuning constants are configurable via environment variables.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from collections import deque

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    logger.warning("opencv/numpy not installed — BeltTachometer will be non-functional")


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_NORMAL = "NORMAL"
STATUS_SLOW = "SLOW"
STATUS_MISTRACK = "MISTRACK"
STATUS_STOPPED = "STOPPED"


class BeltTachometer:
    """Track orange tape on a conveyor belt to derive RPM and detect faults."""

    def __init__(self) -> None:
        # HSV mask range (bright orange tape)
        self.orange_h_low = int(os.getenv("ORANGE_H_LOW", "5"))
        self.orange_h_high = int(os.getenv("ORANGE_H_HIGH", "25"))
        self.orange_s_low = int(os.getenv("ORANGE_S_LOW", "150"))
        self.orange_v_low = int(os.getenv("ORANGE_V_LOW", "150"))

        # Timing / thresholds
        self.crossing_debounce_sec = float(os.getenv("CROSSING_DEBOUNCE_SEC", "0.1"))
        self.slow_threshold_pct = float(os.getenv("SLOW_THRESHOLD_PCT", "80"))
        self.mistrack_threshold_px = int(os.getenv("MISTRACK_THRESHOLD_PX", "50"))
        self.stopped_timeout_sec = float(os.getenv("STOPPED_TIMEOUT_SEC", "3.0"))
        clip_buffer_frames = int(os.getenv("CLIP_BUFFER_FRAMES", "150"))

        # Minimum contour area to consider (filters noise)
        self.min_contour_area = 500

        # State
        self.crossing_times: deque[float] = deque(maxlen=10)
        self.belt_center_x: int | None = None  # calibrated on first detection
        self.baseline_rpm: float | None = None  # set after 5 crossings
        self.frame_buffer: deque[np.ndarray] = deque(maxlen=clip_buffer_frames)

        # Crossing detection state
        self._last_crossing_time: float = 0.0
        self._prev_above_center: bool | None = None  # was tape above centerline?

        # Last reading cache
        self._last_reading: dict = {
            "rpm": 0.0,
            "belt_speed_pct": 0.0,
            "tracking_offset_px": 0,
            "status": STATUS_STOPPED,
            "annotated_frame": None,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> dict:
        """Process a single BGR frame. Returns tachometer reading dict.

        Returns:
            {rpm, belt_speed_pct, tracking_offset_px, status, annotated_frame}
        """
        if cv2 is None:
            return self._last_reading

        now = time.monotonic()
        h, w = frame.shape[:2]
        centerline_y = h // 2

        # Store raw frame for clip buffer
        self.frame_buffer.append(frame.copy())

        # 1. Convert BGR → HSV and apply orange mask
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = np.array([self.orange_h_low, self.orange_s_low, self.orange_v_low])
        upper = np.array([self.orange_h_high, 255, 255])
        mask = cv2.inRange(hsv, lower, upper)

        # 2. Find contours, pick largest
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [c for c in contours if cv2.contourArea(c) >= self.min_contour_area]

        # Annotated frame starts as a copy
        annotated = frame.copy()

        # Draw centerline
        cv2.line(annotated, (0, centerline_y), (w, centerline_y), (0, 255, 255), 1)

        if not contours:
            # No orange detected — check if stopped
            status = self._check_stopped(now)
            self._last_reading = {
                "rpm": self._compute_rpm(),
                "belt_speed_pct": self._compute_speed_pct(),
                "tracking_offset_px": 0,
                "status": status,
                "annotated_frame": annotated,
            }
            self._draw_overlay(annotated, self._last_reading)
            return self._last_reading

        # Pick largest contour
        largest = max(contours, key=cv2.contourArea)

        # 3. Compute centroid
        M = cv2.moments(largest)
        if M["m00"] == 0:
            status = self._check_stopped(now)
            self._last_reading["status"] = status
            self._last_reading["annotated_frame"] = annotated
            self._draw_overlay(annotated, self._last_reading)
            return self._last_reading

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        # 4. Calibrate belt_center_x on first detection
        if self.belt_center_x is None:
            self.belt_center_x = cx

        # 5. Track tape crossing the virtual centerline (Y axis)
        above_center = cy < centerline_y
        if self._prev_above_center is not None and above_center != self._prev_above_center:
            # Tape crossed the centerline — debounce
            if (now - self._last_crossing_time) >= self.crossing_debounce_sec:
                self.crossing_times.append(now)
                self._last_crossing_time = now
                # Set baseline after 5 crossings
                if self.baseline_rpm is None and len(self.crossing_times) >= 5:
                    self.baseline_rpm = self._compute_rpm()
        self._prev_above_center = above_center

        # 6. Compute metrics
        rpm = self._compute_rpm()
        speed_pct = self._compute_speed_pct()
        offset_px = cx - self.belt_center_x

        # 7. Determine status
        status = self._determine_status(now, speed_pct, offset_px)

        # 8. Draw annotations
        cv2.drawContours(annotated, [largest], -1, (0, 255, 0), 2)
        cv2.circle(annotated, (cx, cy), 6, (0, 0, 255), -1)

        self._draw_overlay(annotated, {
            "rpm": rpm, "belt_speed_pct": speed_pct,
            "tracking_offset_px": offset_px, "status": status,
        })

        self._last_reading = {
            "rpm": rpm,
            "belt_speed_pct": speed_pct,
            "tracking_offset_px": offset_px,
            "status": status,
            "annotated_frame": annotated,
        }
        return self._last_reading

    def get_clip_buffer(self) -> bytes:
        """Write buffered frames to an in-memory mp4 and return raw bytes."""
        if cv2 is None or len(self.frame_buffer) == 0:
            return b""

        frames = list(self.frame_buffer)
        h, w = frames[0].shape[:2]

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(tmp_path, fourcc, 30.0, (w, h))
            for f in frames:
                writer.write(f)
            writer.release()

            with open(tmp_path, "rb") as fh:
                return fh.read()
        except Exception:
            logger.exception("Failed to encode clip buffer")
            return b""
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_rpm(self) -> float:
        """Compute RPM from average interval between crossings.

        Each full revolution produces 2 crossings (tape enters and exits
        the centerline), so RPM = 60 / (avg_interval * 2).
        """
        if len(self.crossing_times) < 2:
            return 0.0
        intervals = [
            self.crossing_times[i] - self.crossing_times[i - 1]
            for i in range(1, len(self.crossing_times))
        ]
        avg = sum(intervals) / len(intervals)
        if avg <= 0:
            return 0.0
        # 2 crossings per revolution (enter + exit centerline)
        return 60.0 / (avg * 2)

    def _compute_speed_pct(self) -> float:
        """Belt speed as a percentage of baseline RPM."""
        if self.baseline_rpm is None or self.baseline_rpm <= 0:
            return 100.0  # no baseline yet — assume normal
        rpm = self._compute_rpm()
        return (rpm / self.baseline_rpm) * 100.0

    def _check_stopped(self, now: float) -> str:
        """Return STOPPED if no crossing within timeout, else last status."""
        if not self.crossing_times:
            return STATUS_STOPPED
        elapsed = now - self.crossing_times[-1]
        if elapsed >= self.stopped_timeout_sec:
            return STATUS_STOPPED
        return self._last_reading.get("status", STATUS_NORMAL)

    def _determine_status(self, now: float, speed_pct: float, offset_px: int) -> str:
        """Determine belt status from current metrics."""
        # Check stopped first
        if self.crossing_times:
            elapsed = now - self.crossing_times[-1]
            if elapsed >= self.stopped_timeout_sec:
                return STATUS_STOPPED

        # Check mistrack
        if abs(offset_px) > self.mistrack_threshold_px:
            return STATUS_MISTRACK

        # Check slow (only if baseline is established)
        if self.baseline_rpm is not None and speed_pct < self.slow_threshold_pct:
            return STATUS_SLOW

        return STATUS_NORMAL

    @staticmethod
    def _draw_overlay(frame: np.ndarray, reading: dict) -> None:
        """Draw status text overlay on annotated frame."""
        if cv2 is None:
            return
        status = reading.get("status", "?")
        rpm = reading.get("rpm", 0.0)
        speed = reading.get("belt_speed_pct", 0.0)
        offset = reading.get("tracking_offset_px", 0)

        color = {
            STATUS_NORMAL: (0, 255, 0),
            STATUS_SLOW: (0, 165, 255),
            STATUS_MISTRACK: (0, 0, 255),
            STATUS_STOPPED: (0, 0, 255),
        }.get(status, (255, 255, 255))

        lines = [
            f"Status: {status}",
            f"RPM: {rpm:.1f}",
            f"Speed: {speed:.0f}%",
            f"Offset: {offset}px",
        ]
        for i, line in enumerate(lines):
            cv2.putText(
                frame, line, (10, 25 + i * 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
            )
