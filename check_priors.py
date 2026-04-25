import os
import time

import numpy as np
import pyautogui
import pytesseract
import win32con
import win32gui
from PIL import Image, ImageGrab

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\john.grieve\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

SCREENSHOTS_DIR = os.path.join(os.path.expanduser("~"), "screenshots")
OCR_REGION     = (1780, 620, 2540, 2000)
DATE_REGION    = (2320, 505, 2522, 524)
WINDOW_POS     = (1300, 290, 1250, 1770)   # left, top, width, height


def _get_visible_hwnds():
    hwnds = set()
    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            hwnds.add(hwnd)
    win32gui.EnumWindows(cb, None)
    return hwnds


def _mask_background_for_ocr(img, bg_hex="2e2b28", tolerance=40):
    """Pixels close to bg_hex → white (background); everything else → black (text)."""
    r, g, b = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
    arr = np.array(img.convert("RGB"))
    diff = np.abs(arr.astype(int) - np.array([r, g, b]))
    is_bg = np.all(diff <= tolerance, axis=2)
    result = np.zeros_like(arr)
    result[is_bg] = [255, 255, 255]
    return Image.fromarray(result)


def _images_identical(img_a, img_b):
    return img_a.size == img_b.size and np.array_equal(np.array(img_a), np.array(img_b))


def _focus_window(hwnd):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # Fallback: click the centre of the window
        left, top, width, height = WINDOW_POS
        pyautogui.click(left + width // 2, top + height // 2)
    time.sleep(0.3)


def check_priors():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    def _find_search_tool():
        result = []
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and "Search Tool" in win32gui.GetWindowText(hwnd):
                result.append(hwnd)
        win32gui.EnumWindows(cb, None)
        return result[0] if result else None

    # Focus IntelliViewer and open priors window
    pyautogui.click(80, 300)
    time.sleep(0.3)

    hwnd = _find_search_tool()
    if hwnd:
        print(f"Priors window already open: '{win32gui.GetWindowText(hwnd)}'")
    else:
        before = _get_visible_hwnds()
        pyautogui.press("v")
        time.sleep(1.0)
        new_hwnds = _get_visible_hwnds() - before
        if not new_hwnds:
            print("No new window detected after pressing 'v'")
            return
        hwnd = next(iter(new_hwnds))
        print(f"Found priors window: '{win32gui.GetWindowText(hwnd)}'")

    # Position and size the window
    left, top, width, height = WINDOW_POS
    win32gui.MoveWindow(hwnd, left, top, width, height, True)
    time.sleep(0.3)

    _focus_window(hwnd)

    prev_img = None
    most_recent_prior = None

    for i in range(1, 5):
        pyautogui.press("down")
        time.sleep(0.3)

        img = ImageGrab.grab(bbox=OCR_REGION, all_screens=True)

        if prev_img is not None and _images_identical(img, prev_img):
            print(f"Prior {i} identical to previous — end of list")
            break

        # Scale up so ~10px text becomes ~30px for OCR
        scale = 3
        img_scaled = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)

        img_masked = _mask_background_for_ocr(img_scaled)
        img_masked.save(os.path.join(SCREENSHOTS_DIR, f"prior{i}_masked.png"))

        text = pytesseract.image_to_string(img_masked)

        # Capture and OCR the exam date
        date_img = ImageGrab.grab(bbox=DATE_REGION, all_screens=True)
        date_scaled = date_img.resize((date_img.width * scale, date_img.height * scale), Image.LANCZOS)
        date_masked = _mask_background_for_ocr(date_scaled, bg_hex="333333")
        date_masked.save(os.path.join(SCREENSHOTS_DIR, f"prior{i}_date_masked.png"))
        date_text = pytesseract.image_to_string(date_masked, config="--psm 7").strip()
        print(f"  Date: {date_text}")

        full_text = f"Examination date: {date_text}\n\n{text}" if date_text else text

        txt_path = os.path.join(SCREENSHOTS_DIR, f"prior{i}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"Saved: prior{i}.txt")
        print(f"  {text[:120].strip()}")

        if most_recent_prior is None:
            most_recent_prior = full_text

        prev_img = img

    _focus_window(hwnd)
    pyautogui.hotkey("alt", "f4")
    time.sleep(0.3)
    print("Done.")
    return most_recent_prior


if __name__ == "__main__":
    check_priors()
