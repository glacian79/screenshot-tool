import glob
import os
import re
import time

import numpy as np
import pyautogui
import pytesseract
from PIL import Image, ImageGrab

from screenshot import crop_black_borders, grey_near_color, mask_color_for_ocr

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\john.grieve\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

SCREENSHOTS_DIR = os.path.join(os.path.expanduser("~"), "screenshots")

DEMOG_REGION   = (800, 300, 1270, 500)
ACC_REGION     = (14, 302, 550, 530)
VIEWER_REGION = (20, 300, 1270, 2060)
CLARIO_REGION = (-2100, 1100, -1210, 1960)


def setup_inteliviewer():
    pyautogui.click(80, 300)
    time.sleep(0.3)
    pyautogui.press("3")
    time.sleep(0.5)
    for _ in range(8):
        pyautogui.press("pageup")
        time.sleep(0.1)
    time.sleep(0.3)


def capture_demographics():
    """OCR the demographics region and return (sex, age_raw) or (None, None)."""
    img = ImageGrab.grab(bbox=DEMOG_REGION, all_screens=True)
    scale = 3
    img = img.resize((img.width * scale, img.height * scale))
    masked = mask_color_for_ocr(img)
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    masked.save(os.path.join(SCREENSHOTS_DIR, "demographics.png"))

    config = "--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]()| ^abcdefghijklmnopqrstuvwxyz"
    text = pytesseract.image_to_string(masked, config=config)
    print(f"Demographics OCR raw:\n{text}")

    text = (text.replace("(", "[").replace(")", "]").replace("L", "[")
               .replace("|", "]").replace("O", "0").replace("o", "0"))

    sex_match = re.search(r'\[([MF])\]', text, re.IGNORECASE)
    if not sex_match:
        sex_match = re.search(r'\b([MF])\b(?=\s+\d{1,3}[DWMY]\b)', text, re.IGNORECASE)

    age_match = re.search(r'[\[\(](\d{1,4}\s*[DWMY])[\]\)]', text, re.IGNORECASE)
    if not age_match:
        age_match = re.search(r'\b[MF]\s+(\d{1,4}[DWMY])\b', text, re.IGNORECASE)

    sex = sex_match.group(1).upper() if sex_match else None
    age_raw = age_match.group(1).replace(" ", "").upper() if age_match else None
    if age_raw:
        # Strip leading zeros added by O→0 substitution (e.g. "0033Y" → "33Y")
        age_raw = re.sub(r'^0+(\d)', r'\1', age_raw)
    print(f"Parsed: Sex={sex}, Age={age_raw}")
    return sex, age_raw


def capture_accession_number():
    """OCR the accession number region and save it to accessionNo.txt. Returns the accession string or None."""
    img = ImageGrab.grab(bbox=ACC_REGION, all_screens=True)
    scale = 3
    img = img.resize((img.width * scale, img.height * scale))
    masked = mask_color_for_ocr(img)
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    masked.save(os.path.join(SCREENSHOTS_DIR, "accession.png"))

    config = "--psm 6 --oem 3"
    text = pytesseract.image_to_string(masked, config=config)

    match = re.search(r'Acc\s*#\s*([^\n]+)', text, re.IGNORECASE)
    accession = re.sub(r'\s+', '', match.group(1)) if match else None
    print(f"Accession number: {accession}")

    acc_path = os.path.join(SCREENSHOTS_DIR, "accessionNo.txt")
    with open(acc_path, "w", encoding="utf-8") as f:
        f.write(f"{accession if accession else ''}\n\n--- OCR raw ---\n{text}")
    return accession


def _images_identical(img_a, img_b):
    return img_a.size == img_b.size and np.array_equal(np.array(img_a), np.array(img_b))


def _extract_clinical_from_ocr(text):
    """Return extracted clinical text after 'order/details:', or None."""
    text = re.sub(r"(?i)(?<=order/details:)\n\n", " ", text)
    match = re.search(r"order/details:(.*?)\n\n", text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None


def acquire_images():
    """
    Capture viewer images in a loop, classify them, and return (xray_paths, clinical_text).
    Falls back to Clario region if no clinical info found in viewer images.
    """
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    # Clean up stale outputs from previous runs
    for pattern in ("xray*.png", "clinicalInformation.png", "image*.png", "clario_clinical_info.png"):
        for f in glob.glob(os.path.join(SCREENSHOTS_DIR, pattern)):
            os.remove(f)

    # Wait for the first image to load — retry up to 3 times (4s each) if all black
    for attempt in range(1, 4):
        first_img = ImageGrab.grab(bbox=VIEWER_REGION, all_screens=True)
        pixels = list(first_img.convert("L").getdata())
        if sum(1 for p in pixels if p < 10) / len(pixels) < 0.95:
            break
        print(f"First image appears black (attempt {attempt}/3), waiting 4s...")
        time.sleep(4)
    else:
        raise RuntimeError("Viewer image still black after 12 seconds — image may not have loaded")

    raw_paths = []
    prev_img = None

    for i in range(1, 13):
        img = ImageGrab.grab(bbox=VIEWER_REGION, all_screens=True)
        if prev_img is not None and _images_identical(img, prev_img):
            print(f"Frame {i} identical to previous — end of stack")
            break
        path = os.path.join(SCREENSHOTS_DIR, f"image{i}.png")
        img.save(path)
        print(f"Captured: {path}")
        raw_paths.append(path)
        prev_img = img
        pyautogui.press("pagedown")
        time.sleep(0.3)

    # Classify: find clinical info image vs xray images
    clinical_text = None
    clinical_source = None
    xray_sources = []

    for path in raw_paths:
        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        txt_path = os.path.join(SCREENSHOTS_DIR, os.path.basename(path).replace(".png", "_ocr.txt"))
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        if re.search(r"order/details:", text, re.IGNORECASE):
            extracted = _extract_clinical_from_ocr(text)
            if extracted and clinical_text is None:
                clinical_text = extracted
                clinical_source = path
                print(f"Clinical info found in {os.path.basename(path)}")
        else:
            xray_sources.append(path)

    # Rename clinical image
    if clinical_source:
        dst = os.path.join(SCREENSHOTS_DIR, "clinicalInformation.png")
        os.replace(clinical_source, dst)
        print("Renamed to clinicalInformation.png")

    # Crop black borders and rename xray images
    xray_paths = []
    for idx, src in enumerate(xray_sources, start=1):
        dst = os.path.join(SCREENSHOTS_DIR, f"xray{idx}.png")
        img = Image.open(src)
        img = grey_near_color(img)
        img = crop_black_borders(img)
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
        img.save(dst)
        os.remove(src)
        xray_paths.append(dst)
        print(f"Saved: xray{idx}.png")

    # Fallback: capture Clario region if no clinical info found
    if clinical_text is None:
        print("No clinical info in viewer images — trying Clario region...")
        clario_img = ImageGrab.grab(bbox=CLARIO_REGION, all_screens=True)
        clario_img_ocr = clario_img.resize((clario_img.width * 4, clario_img.height * 4), Image.LANCZOS)
        clario_path = os.path.join(SCREENSHOTS_DIR, "clario_clinical_info.png")
        clario_img_ocr.save(clario_path)
        clario_text = pytesseract.image_to_string(clario_img_ocr)
        _clario_matches = re.findall(r"clinical information:(.*?)\n\n", clario_text, re.DOTALL | re.IGNORECASE)
        if _clario_matches:
            clinical_text = "  ".join(m.strip() for m in _clario_matches if m.strip()) or None
        else:
            clinical_text = clario_text.strip() or None
        if clinical_text:
            print("Clinical info found in Clario region")
        else:
            print("No clinical info found in Clario region either")

    # Save clinical text to file
    if clinical_text:
        txt_path = os.path.join(SCREENSHOTS_DIR, "clinicalInformation.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(clinical_text)
        print(f"Clinical information saved: {txt_path}")

    return xray_paths, clinical_text


def run_capture_workflow():
    """Full acquisition workflow. Returns (xray_paths, clinical_text, sex, age_raw)."""
    setup_inteliviewer()
    sex, age_raw = capture_demographics()
    capture_accession_number()
    pyautogui.press('o')
    xray_paths, clinical_text = acquire_images()
    pyautogui.press('o')
    return xray_paths, clinical_text, sex, age_raw
