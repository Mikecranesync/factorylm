#!/usr/bin/env python3
"""
Factory I/O Automator
====================
Provides automation for Factory I/O simulation:
- Mouse control for fault injection
- Screenshot capture
- Scene control via keyboard shortcuts

Usage:
    python factoryio_automator.py <command> [args]

Commands:
    screenshot          - Take a screenshot of Factory I/O
    click <x> <y>       - Click at coordinates
    push_box            - Push a box off the conveyor (random location)
    inject_fault <type> - Inject a specific fault
    get_mouse_pos       - Get current mouse position
    move_to <x> <y>     - Move mouse to position
    press <key>         - Press a keyboard key

Deployment:
    This script should be deployed to the PLC laptop and called via Jarvis Node API:
    curl -X POST http://100.72.2.99:8765/shell -H "Content-Type: application/json" \
        -d '{"command": "python C:/Users/hharp/OneDrive/Desktop/FactoryLM/scripts/factoryio_automator.py <command>"}'
"""
import sys
import time
import random
import base64
from io import BytesIO

import pyautogui
import mss
import mss.tools

# Disable PyAutoGUI failsafe (for headless operation)
pyautogui.FAILSAFE = False

# Factory I/O window coordinates (adjust based on your setup)
# These are approximate - may need calibration
FACTORYIO_BOUNDS = {
    "left": 0,
    "top": 0,
    "width": 1600,
    "height": 900
}

# Common conveyor positions for box pushing (relative to Factory I/O window)
CONVEYOR_POSITIONS = [
    (417, 333),   # Position 1 (scaled from 1920x1080)
    (583, 333),   # Position 2
    (750, 333),   # Position 3
    (917, 333),   # Position 4
]

def take_screenshot():
    """Capture screenshot and return as base64."""
    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[1])  # Primary monitor
        img_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        return {"success": True, "image_base64": b64, "size": [screenshot.width, screenshot.height]}

def click_at(x, y):
    """Click at specified coordinates."""
    pyautogui.click(x, y)
    return {"success": True, "clicked_at": [x, y]}

def push_box():
    """Push a box off the conveyor by clicking and dragging."""
    # Pick a random conveyor position
    start = random.choice(CONVEYOR_POSITIONS)
    # Drag direction (off the conveyor)
    end = (start[0], start[1] + 200)  # Push downward

    pyautogui.moveTo(start[0], start[1], duration=0.2)
    time.sleep(0.1)
    pyautogui.mouseDown()
    pyautogui.moveTo(end[0], end[1], duration=0.3)
    pyautogui.mouseUp()

    return {"success": True, "action": "push_box", "from": start, "to": end}

def inject_fault(fault_type):
    """Inject a specific fault type."""
    faults = {
        "sensor_fail": lambda: click_at(300, 500),  # Example: click sensor to toggle
        "motor_stop": lambda: pyautogui.press('space'),  # Example: stop/start
        "box_jam": push_box,
        "emergency": lambda: pyautogui.press('e'),  # E-stop if mapped
    }

    if fault_type in faults:
        result = faults[fault_type]()
        return {"success": True, "fault_injected": fault_type, "details": result}
    else:
        return {"success": False, "error": f"Unknown fault type: {fault_type}", "available": list(faults.keys())}

def get_mouse_position():
    """Get current mouse position."""
    pos = pyautogui.position()
    return {"x": pos.x, "y": pos.y}

def move_mouse(x, y):
    """Move mouse to position."""
    pyautogui.moveTo(x, y, duration=0.3)
    return {"success": True, "moved_to": [x, y]}

def press_key(key):
    """Press a keyboard key."""
    pyautogui.press(key)
    return {"success": True, "pressed": key}

def main():
    import json

    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command specified", "usage": __doc__}))
        return

    cmd = sys.argv[1].lower()

    try:
        if cmd == "screenshot":
            result = take_screenshot()
        elif cmd == "click" and len(sys.argv) >= 4:
            result = click_at(int(sys.argv[2]), int(sys.argv[3]))
        elif cmd == "push_box":
            result = push_box()
        elif cmd == "inject_fault" and len(sys.argv) >= 3:
            result = inject_fault(sys.argv[2])
        elif cmd == "get_mouse_pos":
            result = get_mouse_position()
        elif cmd == "move_to" and len(sys.argv) >= 4:
            result = move_mouse(int(sys.argv[2]), int(sys.argv[3]))
        elif cmd == "press" and len(sys.argv) >= 3:
            result = press_key(sys.argv[2])
        else:
            result = {"error": f"Unknown command: {cmd}", "available": ["screenshot", "click", "push_box", "inject_fault", "get_mouse_pos", "move_to", "press"]}

        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
