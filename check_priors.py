import os
import re
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
INFO_REGION    = (1910, 460, 2526, 628)
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

    # Close priors window if already open
    existing = _find_search_tool()
    if existing:
        print("Closing existing priors window...")
        win32gui.SetForegroundWindow(existing)
        time.sleep(0.2)
        pyautogui.click(1923, 2032)
        time.sleep(0.5)

    # Focus IntelliViewer and open fresh priors window
    pyautogui.click(620, 500)
    time.sleep(0.3)
    pyautogui.press("v")
    time.sleep(1.0)

    hwnd = _find_search_tool()
    if not hwnd:
        print("No priors window detected after pressing 'v'")
        return
    print(f"Found priors window: '{win32gui.GetWindowText(hwnd)}'")

    # Position and size the window
    left, top, width, height = WINDOW_POS
    win32gui.MoveWindow(hwnd, left, top, width, height, True)
    time.sleep(0.3)

    _focus_window(hwnd)
    pyautogui.press("down")
    time.sleep(0.5)

    prev_img = None
    most_recent_prior = None

    for i in range(1, 5):
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

        # Capture the info panel: prior title, date, and accession number
        info_img = ImageGrab.grab(bbox=INFO_REGION, all_screens=True)
        info_scaled = info_img.resize((info_img.width * scale, info_img.height * scale), Image.LANCZOS)
        info_masked = _mask_background_for_ocr(info_scaled, bg_hex="333333")
        info_masked.save(os.path.join(SCREENSHOTS_DIR, f"prior{i}_info_masked.png"))
        info_text = pytesseract.image_to_string(info_masked, config="--psm 6")

        date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', info_text)
        acc_match  = re.search(r'Accession Number:\s*(\S+)', info_text, re.IGNORECASE)
        first_line = next((l.strip() for l in info_text.splitlines()
                           if l.strip() and 'refresh' not in l.lower()), "")
        prior_title = re.sub(r'\d{1,2}\s+\w+\s+\d{4}.*', '', first_line).strip()

        date_text  = date_match.group(1) if date_match else ""
        acc_text   = acc_match.group(1)  if acc_match  else ""
        print(f"  Prior title: {prior_title}")
        print(f"  Date: {date_text}")
        print(f"  Prior accession: {acc_text}")

        header_parts = []
        if prior_title:
            header_parts.append(f"Prior title: {prior_title}")
        if date_text:
            header_parts.append(f"Examination date: {date_text}")
        if acc_text:
            header_parts.append(f"Prior accession number: {acc_text}")
        header = "\n".join(header_parts)
        full_text = f"{header}\n\n{text}" if header else text

        txt_path = os.path.join(SCREENSHOTS_DIR, f"prior{i}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"Saved: prior{i}.txt")
        print(f"  {text[:120].strip()}")

        if most_recent_prior is None:
            most_recent_prior = full_text

        prev_img = img
        _focus_window(hwnd)
        pyautogui.press("down")
        time.sleep(0.5)

    pyautogui.click(1923, 2032)
    time.sleep(0.3)
    print("Done.")
    return most_recent_prior


if __name__ == "__main__":
    check_priors()
