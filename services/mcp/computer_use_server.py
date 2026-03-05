"""MCP server for desktop computer control.

Exposes screenshot, click, type, key press, scroll, mouse move, drag,
and cursor position tools using pyautogui + PIL. Designed for GUI
automation of Factory I/O, PLC software, and any desktop app.
"""

from __future__ import annotations

import base64
import io
import logging
import time

import pyautogui
from mcp.server.fastmcp import FastMCP, Image
from PIL import ImageGrab
from screeninfo import get_monitors

logger = logging.getLogger(__name__)

app = FastMCP("factorylm-computer-use")

# Disable pyautogui's fail-safe (moving mouse to corner aborts) — we want
# full control for automation.
pyautogui.FAILSAFE = False

TYPING_DELAY_MS = 12


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_screen_bbox(screen_index: int = 0) -> tuple[int, int, int, int]:
    """Return (x, y, x+w, y+h) bounding box for the given screen."""
    screens = sorted(get_monitors(), key=lambda s: s.x)
    if screen_index < 0 or screen_index >= len(screens):
        raise IndexError(f"Invalid screen index {screen_index}, have {len(screens)} screens")
    s = screens[screen_index]
    return (s.x, s.y, s.x + s.width, s.y + s.height)


def _grab_screenshot(screen_index: int = 0) -> bytes:
    """Capture a screenshot of the specified screen, return PNG bytes."""
    bbox = _get_screen_bbox(screen_index)
    img = ImageGrab.grab(bbox=bbox, all_screens=True)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@app.tool()
def screenshot(screen_index: int = 0) -> Image:
    """Take a screenshot of the desktop.

    Args:
        screen_index: Which monitor to capture (0 = primary). Defaults to 0.

    Returns an image that Claude can see.
    """
    time.sleep(0.5)  # brief settle time
    png_bytes = _grab_screenshot(screen_index)
    return Image(data=base64.b64encode(png_bytes).decode(), format="png")


@app.tool()
def click(x: int, y: int, button: str = "left") -> str:
    """Click at the given screen coordinates.

    Args:
        x: X pixel coordinate.
        y: Y pixel coordinate.
        button: One of "left", "right", "double", "middle". Defaults to "left".
    """
    if button == "left":
        pyautogui.click(x, y)
    elif button == "right":
        pyautogui.rightClick(x, y)
    elif button == "double":
        pyautogui.doubleClick(x, y)
    elif button == "middle":
        pyautogui.middleClick(x, y)
    else:
        return f"Unknown button '{button}'. Use left, right, double, or middle."
    return f"Clicked {button} at ({x}, {y})"


@app.tool()
def type_text(text: str) -> str:
    """Type text using the keyboard. Types into whatever is currently focused.

    Args:
        text: The text string to type.
    """
    pyautogui.typewrite(text, interval=TYPING_DELAY_MS / 1000)
    return f"Typed: {text}"


@app.tool()
def key_press(keys: str) -> str:
    """Press a key or key combination.

    Args:
        keys: Key combo like "ctrl+c", "enter", "alt+tab", "ctrl+shift+s".
    """
    key_list = [k.strip().lower() for k in keys.split("+")]
    # Map common aliases
    key_map = {
        "super_l": "win", "super": "win", "command": "win",
        "escape": "esc", "page_down": "pagedown", "page_up": "pageup",
    }
    key_list = [key_map.get(k, k) for k in key_list]

    for k in key_list:
        pyautogui.keyDown(k)
    for k in reversed(key_list):
        pyautogui.keyUp(k)
    return f"Pressed: {keys}"


@app.tool()
def scroll(x: int, y: int, direction: str = "down", amount: int = 5) -> str:
    """Scroll at the given coordinates.

    Args:
        x: X pixel coordinate.
        y: Y pixel coordinate.
        direction: One of "up", "down", "left", "right". Defaults to "down".
        amount: Number of scroll clicks. Defaults to 5.
    """
    if direction in ("up", "down"):
        clicks = amount if direction == "up" else -amount
        pyautogui.scroll(clicks, x, y)
    elif direction in ("left", "right"):
        clicks = amount if direction == "right" else -amount
        pyautogui.hscroll(clicks, x, y)
    else:
        return f"Unknown direction '{direction}'. Use up, down, left, or right."
    return f"Scrolled {direction} by {amount} at ({x}, {y})"


@app.tool()
def mouse_move(x: int, y: int) -> str:
    """Move the mouse cursor to the given coordinates.

    Args:
        x: X pixel coordinate.
        y: Y pixel coordinate.
    """
    pyautogui.moveTo(x, y)
    return f"Moved mouse to ({x}, {y})"


@app.tool()
def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> str:
    """Drag from one point to another.

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        end_x: Ending X coordinate.
        end_y: Ending Y coordinate.
        duration: How long the drag takes in seconds. Defaults to 0.5.
    """
    pyautogui.moveTo(start_x, start_y)
    pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration)
    return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"


@app.tool()
def cursor_position() -> str:
    """Get the current mouse cursor position.

    Returns coordinates as "X=100,Y=200".
    """
    x, y = pyautogui.position()
    return f"X={x},Y={y}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
