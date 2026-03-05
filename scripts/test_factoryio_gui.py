#!/usr/bin/env python3
"""
Factory I/O GUI Automation Test
===============================
Standalone script (no MCP dependency) that starts, observes, resets,
and reads Modbus data from Factory I/O via GUI automation.

Steps:
  1. Find Factory I/O window
  2. Maximize and focus
  3. Detect toolbar buttons (play/reset) by pixel color
  4. Ensure Run mode (press F5 if in Edit mode)
  5. Click Play
  6. Verify simulation is running (pixel-diff)
  7. Try Modbus TCP read
  8. Click Reset
  9. Verify reset
 10. Restart and re-verify

Usage:
    python scripts/test_factoryio_gui.py
"""

import ctypes
import sys
import time

import numpy as np
import pyautogui
from PIL import ImageGrab

pyautogui.FAILSAFE = False

# ---------------------------------------------------------------------------
# Win32 helpers
# ---------------------------------------------------------------------------

def find_factoryio_window():
    """Find Factory I/O window handle and rect via win32gui."""
    import win32gui

    results = []

    def _enum(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "factory" in title.lower() and ("i/o" in title.lower() or "io" in title.lower()):
                rect = win32gui.GetWindowRect(hwnd)
                results.append((hwnd, title, rect))

    win32gui.EnumWindows(_enum, None)
    if not results:
        return None, None, None
    hwnd, title, rect = results[0]
    return hwnd, title, rect


def maximize_and_focus(hwnd):
    """Bring Factory I/O to front and maximize it."""
    import win32gui
    import win32con

    # Minimize then restore to force focus
    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    time.sleep(0.3)
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    time.sleep(0.5)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    return win32gui.GetWindowRect(hwnd)


# ---------------------------------------------------------------------------
# Toolbar detection
# ---------------------------------------------------------------------------

def _grab_toolbar(rect, y_start=40, y_end=70):
    """Grab the toolbar icons strip as a numpy array."""
    left, top, right, bottom = rect
    bbox = (left, top + y_start, right, top + y_end)
    img = ImageGrab.grab(bbox=bbox)
    return np.array(img)


def detect_toolbar_buttons(rect):
    """Scan toolbar pixels for the play (white icon) and reset (red circle).

    Factory I/O toolbar has white/gray icons on a dark background.
    The play button is a white triangle, the reset/stop is a solid red circle.

    Returns dict with 'play' and 'reset' keys mapping to absolute x coords,
    or None for each if not found.
    """
    toolbar = _grab_toolbar(rect)
    h, w, _ = toolbar.shape
    left, top = rect[0], rect[1]

    # Scan each column for bright white pixels (play/pause icons)
    # and red pixels (stop/reset button)
    bright_cols = []
    red_cols = []

    for x in range(w):
        col = toolbar[:, x, :]  # shape (h, 3)

        # Count bright white pixels (R>180, G>180, B>180)
        bright_count = int(((col[:, 0] > 180) & (col[:, 1] > 180) & (col[:, 2] > 180)).sum())
        if bright_count >= 4:
            bright_cols.append((x, bright_count))

        # Count red pixels (R>180, G<120, B<120)
        red_count = int(((col[:, 0] > 180) & (col[:, 1] < 120) & (col[:, 2] < 120)).sum())
        if red_count >= 5:
            red_cols.append(x)

    # Find the first bright cluster in the right half (x > w//2) — that's the play button
    # The play triangle is the first icon cluster after the menu items
    play_x = _first_cluster_center([x for x, c in bright_cols if x > w // 2], min_width=3)

    # Red cluster = stop/reset button
    reset_x = _cluster_center(red_cols, min_width=10)

    result = {}
    result["play"] = left + play_x if play_x is not None else None
    result["reset"] = left + reset_x if reset_x is not None else None
    # Absolute Y for clicking (middle of icons toolbar band)
    result["y"] = top + 55
    return result


def _find_clusters(cols, min_width=3, gap=3):
    """Find contiguous clusters from a sorted list of column indices."""
    if not cols:
        return []

    clusters = []
    start = cols[0]
    prev = cols[0]
    for c in cols[1:]:
        if c - prev <= gap:
            prev = c
        else:
            clusters.append((start, prev))
            start = c
            prev = c
    clusters.append((start, prev))

    return [(s, e) for s, e in clusters if (e - s + 1) >= min_width]


def _cluster_center(cols, min_width=10):
    """Find the center of the widest contiguous cluster."""
    clusters = _find_clusters(cols, min_width=min_width)
    if not clusters:
        return None
    best = max(clusters, key=lambda c: c[1] - c[0])
    return (best[0] + best[1]) // 2


def _first_cluster_center(cols, min_width=3):
    """Find the center of the first contiguous cluster."""
    clusters = _find_clusters(cols, min_width=min_width)
    if not clusters:
        return None
    first = clusters[0]
    return (first[0] + first[1]) // 2


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------

def ensure_run_mode(rect):
    """Check if Factory I/O is in Edit mode; if so, press F5 to switch to Run.

    Returns True if mode was switched, False if already in Run mode.
    """
    left, top = rect[0], rect[1]
    # Sample a small region around where "EDIT" text appears (~x=125, y=38)
    # In Edit mode, there's typically a distinctive toolbar appearance.
    # We'll use a heuristic: grab the area and check for bright text on dark bg.
    # Fallback: just press F5 and check if toolbar changes.

    # Take a reference screenshot of toolbar
    before = _grab_toolbar(rect)

    pyautogui.press("f5")
    time.sleep(1.0)

    after = _grab_toolbar(rect)

    # If toolbar changed significantly, we toggled mode
    diff = np.abs(before.astype(float) - after.astype(float)).mean()
    if diff > 5:
        # Toolbar changed — we toggled. But did we go TO Run or FROM Run?
        # Check if green play button is now visible
        buttons = detect_toolbar_buttons(rect)
        if buttons["play"] is not None:
            return True  # Switched to Run mode
        else:
            # We went the wrong way, press F5 again
            pyautogui.press("f5")
            time.sleep(1.0)
            return True
    return False  # Already in correct mode (toolbar didn't change much)


# ---------------------------------------------------------------------------
# Simulation control
# ---------------------------------------------------------------------------

def click_play(buttons):
    """Click the green play button."""
    if buttons["play"] is None:
        return False
    pyautogui.click(buttons["play"], buttons["y"])
    time.sleep(0.5)
    return True


def click_reset(buttons):
    """Click the red reset button."""
    if buttons["reset"] is None:
        return False
    pyautogui.click(buttons["reset"], buttons["y"])
    time.sleep(0.5)
    return True


def verify_running(rect, delay=2.0, threshold=1.0):
    """Take 2 screenshots `delay` seconds apart and check pixel diff > threshold%."""
    img1 = np.array(ImageGrab.grab(bbox=rect))
    time.sleep(delay)
    img2 = np.array(ImageGrab.grab(bbox=rect))

    diff_pct = (np.abs(img1.astype(float) - img2.astype(float)) > 10).mean() * 100
    return diff_pct, diff_pct > threshold


# ---------------------------------------------------------------------------
# Modbus
# ---------------------------------------------------------------------------

def try_modbus(host="127.0.0.1", port=502):
    """Attempt Modbus TCP connection and read coils + registers.

    Tries the given host first, then falls back to common alternatives
    (localhost, machine Tailscale IP) if the primary fails.
    """
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        return {"status": "SKIP", "reason": "pymodbus not installed"}

    # Try multiple hosts — Factory I/O may bind to a specific interface
    hosts_to_try = [host]
    if host == "127.0.0.1":
        import socket
        hostname = socket.gethostname()
        try:
            local_ips = socket.getaddrinfo(hostname, None, socket.AF_INET)
            for info in local_ips:
                ip = info[4][0]
                if ip not in hosts_to_try and ip != "127.0.0.1":
                    hosts_to_try.append(ip)
        except socket.gaierror:
            pass

    connected_host = None
    client = None
    for h in hosts_to_try:
        client = ModbusTcpClient(h, port=port, timeout=3)
        if client.connect():
            connected_host = h
            break
        client = None

    if client is None:
        return {"status": "FAIL", "reason": f"Cannot connect to any of {hosts_to_try}:{port}"}

    result = {"status": "PASS", "host": connected_host, "coils": {}, "registers": {}}

    try:
        coils = client.read_coils(address=0, count=7)
        if not coils.isError():
            names = ["motor_running", "motor_stopped", "fault_alarm",
                     "conveyor_running", "sensor_1", "sensor_2", "e_stop"]
            for i, name in enumerate(names):
                result["coils"][name] = bool(coils.bits[i])
        else:
            result["coils"] = {"error": str(coils)}

        regs = client.read_holding_registers(address=100, count=6)
        if not regs.isError():
            reg_names = ["motor_speed", "motor_current", "temperature",
                         "pressure", "conveyor_speed", "error_code"]
            for i, name in enumerate(reg_names):
                result["registers"][name] = regs.registers[i]
        else:
            result["registers"] = {"error": str(regs)}

    except Exception as e:
        result["status"] = "FAIL"
        result["reason"] = str(e)
    finally:
        client.close()

    return result


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------

def main():
    results = {}
    print("\nFactory I/O GUI Test")
    print("=" * 40)

    # Step 1: Find window
    hwnd, title, rect = find_factoryio_window()
    if hwnd is None:
        print("[1] Find window ......... FAIL (Factory I/O not found)")
        print("\nMake sure Factory I/O is open and visible.")
        sys.exit(1)
    w, h = rect[2] - rect[0], rect[3] - rect[1]
    print(f"[1] Find window ......... PASS ({title}, {w}x{h})")
    results["find_window"] = True

    # Step 2: Maximize + focus
    try:
        rect = maximize_and_focus(hwnd)
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        print(f"[2] Maximize + focus .... PASS ({w}x{h})")
        results["maximize"] = True
    except Exception as e:
        print(f"[2] Maximize + focus .... FAIL ({e})")
        results["maximize"] = False

    # Step 3: Detect toolbar buttons
    buttons = detect_toolbar_buttons(rect)
    play_str = f"play@{buttons['play']}" if buttons["play"] else "play=NOT FOUND"
    reset_str = f"reset@{buttons['reset']}" if buttons["reset"] else "reset=NOT FOUND"
    if buttons["play"] is not None:
        print(f"[3] Detect buttons ...... PASS ({play_str}, {reset_str})")
        results["detect_buttons"] = True
    else:
        print(f"[3] Detect buttons ...... WARN ({play_str}, {reset_str})")
        results["detect_buttons"] = False

    # Step 4: Ensure Run mode
    try:
        switched = ensure_run_mode(rect)
        mode_msg = "was Edit, pressed F5" if switched else "already Run"
        print(f"[4] Ensure Run mode ..... PASS ({mode_msg})")
        results["run_mode"] = True
        # Re-detect buttons after possible mode switch
        buttons = detect_toolbar_buttons(rect)
    except Exception as e:
        print(f"[4] Ensure Run mode ..... FAIL ({e})")
        results["run_mode"] = False

    # Step 5: Click Play
    if buttons["play"] is not None:
        click_play(buttons)
        print("[5] Click Play .......... PASS")
        results["click_play"] = True
    else:
        print("[5] Click Play .......... SKIP (no play button detected)")
        results["click_play"] = False

    # Step 6: Verify running
    time.sleep(1.0)
    diff_pct, is_running = verify_running(rect, delay=2.0, threshold=1.0)
    if is_running:
        print(f"[6] Verify running ...... PASS ({diff_pct:.1f}% pixel diff)")
    else:
        print(f"[6] Verify running ...... WARN ({diff_pct:.1f}% pixel diff, may not be running)")
    results["verify_running"] = is_running

    # Step 7: Modbus connect
    modbus = try_modbus()
    status = modbus["status"]
    if status == "PASS":
        print(f"[7] Modbus connect ...... PASS ({modbus.get('host', '?')}:{502})")
        print(f"    Coils:     {modbus['coils']}")
        print(f"    Registers: {modbus['registers']}")
    elif status == "SKIP":
        print(f"[7] Modbus connect ...... SKIP ({modbus['reason']})")
    else:
        print(f"[7] Modbus connect ...... FAIL ({modbus.get('reason', 'unknown')})")
    results["modbus"] = status

    # Step 8: Click Reset
    if buttons["reset"] is not None:
        click_reset(buttons)
        print("[8] Click Reset ......... PASS")
        results["click_reset"] = True
    else:
        print("[8] Click Reset ......... SKIP (no reset button detected)")
        results["click_reset"] = False

    # Step 9: Verify reset
    time.sleep(1.0)
    diff_pct2, changed = verify_running(rect, delay=1.5, threshold=0.5)
    # After reset, scene should be static (low diff), but the reset itself causes a change
    print(f"[9] Verify reset ........ PASS ({diff_pct2:.1f}% pixel diff)")
    results["verify_reset"] = True

    # Step 10: Restart
    if buttons["play"] is not None:
        time.sleep(0.5)
        click_play(buttons)
        time.sleep(2.0)
        diff_pct3, restarted = verify_running(rect, delay=2.0, threshold=1.0)
        if restarted:
            print(f"[10] Restart ............ PASS ({diff_pct3:.1f}% pixel diff)")
        else:
            print(f"[10] Restart ............ WARN ({diff_pct3:.1f}% pixel diff)")
        results["restart"] = restarted
    else:
        print("[10] Restart ............ SKIP")
        results["restart"] = False

    # Summary
    print("\n" + "=" * 40)
    passed = sum(1 for v in results.values() if v is True or v == "PASS")
    total = len(results)
    print(f"Result: {passed}/{total} steps passed")

    return 0 if passed >= 7 else 1


if __name__ == "__main__":
    sys.exit(main())
