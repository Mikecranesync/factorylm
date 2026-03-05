"""Use image matching to find and click the scene thumbnail."""
import pyautogui
import pygetwindow
import time
from PIL import Image

pyautogui.FAILSAFE = False

log = open(r"C:\Users\hharp\Desktop\auto_click_log.txt", "w")
try:
    # First take a screenshot
    sc = pyautogui.screenshot()
    log.write("Screenshot: %dx%d\n" % (sc.width, sc.height))

    # Crop the "LLM A to B" text area as a search template
    # From region5 (1600x900), the text "LLM A to B" is at roughly (280, 460) to (400, 480)
    # At full 3840x2160, that's the same (since region starts at 0,0)
    template = sc.crop((270, 450, 410, 490))
    template.save(r"C:\Users\hharp\Desktop\template.png")
    log.write("Template saved (text area)\n")

    # Try to locate it on screen
    loc = pyautogui.locateOnScreen(template, confidence=0.7)
    log.write("locateOnScreen result: %s\n" % str(loc))

    if loc:
        # Click slightly above the text (on the thumbnail image)
        cx = loc.left + loc.width // 2
        cy = loc.top - 50  # 50px above the text center = on the thumbnail
        log.write("Clicking at: %d, %d (above text)\n" % (cx, cy))
        pyautogui.click(cx, cy)
        time.sleep(8)
    else:
        log.write("Template not found, trying broader search\n")
        # Try locateAll with lower confidence
        try:
            loc2 = pyautogui.locateOnScreen(template, confidence=0.5)
            log.write("Lower confidence result: %s\n" % str(loc2))
        except Exception as e2:
            log.write("Lower confidence error: %s\n" % str(e2))

        # Fallback: try clicking at the exact physical coords from the screenshot
        # The thumbnail in the screenshot is at approx physical (335, 415)
        log.write("Fallback: clicking physical (335, 415) via pyautogui\n")
        pyautogui.click(335, 415)
        time.sleep(3)
        pyautogui.click(335, 415)
        time.sleep(8)

    # Final screenshot
    wins = pygetwindow.getWindowsWithTitle("Factory IO")
    for w in wins:
        log.write("Title: '%s'\n" % w.title)
    sc2 = pyautogui.screenshot(region=(0, 0, 1600, 900))
    sc2.save(r"C:\Users\hharp\Desktop\screen_region.png")
    log.write("Done\n")

except Exception as e:
    log.write("ERROR: %s\n" % str(e))
    import traceback
    log.write(traceback.format_exc())
finally:
    log.close()
