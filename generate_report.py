import base64
import glob
import os
import re
import time

import anthropic
import pyautogui
import pyperclip
import pytesseract
from PIL import Image, ImageGrab

from ocr_screenshot import capture_and_ocr
from screenshot import crop_black_borders, mask_color_for_ocr

KEY_PATH = r"C:\Users\john.grieve\.claude\API_KEYS\reportgenerator.key"
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\john.grieve\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Screen region containing sex/age, e.g. "[M] [006Y]"
DEMOG_REGION = (900, 400, 3820, 570)


def load_api_key():
    with open(KEY_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def capture_demographics():
    """OCR the demographics region and return (sex, age_str) or (None, None)."""
    img = ImageGrab.grab(bbox=DEMOG_REGION, all_screens=True)

    scale = 3
    img = img.resize((img.width * scale, img.height * scale))
    masked = mask_color_for_ocr(img)

    screenshots_dir = os.path.join(os.path.expanduser("~"), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    masked.save(os.path.join(screenshots_dir, "demographics.png"))

    config = "--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]()| ^abcdefghijklmnopqrstuvwxyz"
    text = pytesseract.image_to_string(masked, config=config)

    print(f"Demographics OCR raw:\n{text}")

    text = text.replace("(", "[").replace(")", "]").replace("L", "[").replace("|", "]").replace("O", "0").replace("o", "0")

    sex_match = re.search(r'\[([MF])\]', text, re.IGNORECASE)
    if not sex_match:
        sex_match = re.search(r'\b([MF])\b(?=\s+\d{1,3}[DWMY]\b)', text, re.IGNORECASE)

    age_match = re.search(r'[\[\(](\d{1,3}\s*[DWMY])[\]\)]', text, re.IGNORECASE)
    if not age_match:
        age_match = re.search(r'\b[MF]\s+(\d{1,3}[DWMY])\b', text, re.IGNORECASE)

    sex = sex_match.group(1).upper() if sex_match else None
    age_raw = age_match.group(1).replace(" ", "").upper() if age_match else None

    print(f"Parsed: Sex={sex}, Age={age_raw}")

    return sex, age_raw


def format_age(age_raw):
    """Convert '006Y' -> '6 years old', '025M' -> '25 months old', etc."""
    m = re.match(r'^(\d+)([DWMY])$', age_raw, re.IGNORECASE)
    if not m:
        return age_raw
    num = int(m.group(1))
    unit = m.group(2).upper()
    unit_names = {"Y": "years", "M": "months", "W": "weeks", "D": "days"}
    return f"{num} {unit_names.get(unit, unit)} old"


def inject_demographics(report_text, sex, age_raw):
    """Prepend sex and age to the content of the HISTORY section."""
    if not sex and not age_raw:
        return report_text

    parts = []
    if sex:
        parts.append("Male" if sex == "M" else "Female")
    if age_raw:
        parts.append(format_age(age_raw))
    demo_str = ", ".join(parts)

    injected = re.sub(
        r'(HISTORY\s*:[ \t]*\n?)',
        lambda m: m.group(0) + demo_str + ". ",
        report_text,
        count=1,
        flags=re.IGNORECASE,
    )

    if injected == report_text:
        injected = f"Patient: {demo_str}\n\n{report_text}"

    return injected


def generate_radiology_report():
    # Capture demographics before the screen changes
    sex, age_raw = capture_demographics()
    if sex or age_raw:
        parts = []
        if sex:
            parts.append("Male" if sex == "M" else "Female")
        if age_raw:
            parts.append(format_age(age_raw))
        print(f"Demographics: {', '.join(parts)}")
    else:
        print("Demographics: not found")

    # Capture screenshots and extract clinical information
    capture_and_ocr()

    screenshots_dir = os.path.join(os.path.expanduser("~"), "screenshots")

    # Find the most recently saved region 1 screenshot
    matches = sorted(glob.glob(os.path.join(screenshots_dir, "screenshot_1_*.png")))
    if not matches:
        print("No region 1 screenshot found")
        return
    region1_path = matches[-1]

    # Read clinical information
    clinical_filepath = os.path.join(screenshots_dir, "clinicalInformation.txt")
    if not os.path.exists(clinical_filepath):
        print("clinicalInformation.txt not found — no text between 'Relevant' and 'IMAGING'")
        return

    with open(clinical_filepath, "r", encoding="utf-8") as f:
        clinical_text = f.read().strip()

    if not clinical_text:
        print("clinicalInformation.txt is empty")
        return

    # Prepend demographics to clinical text
    if sex or age_raw:
        parts = []
        if sex:
            parts.append("Male" if sex == "M" else "Female")
        if age_raw:
            parts.append(format_age(age_raw))
        clinical_text = ", ".join(parts) + ". " + clinical_text

    # Extract title from existing report (first all-caps line)
    pyautogui.click(-1114, 735)
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.3)
    for _ in range(5):
        try:
            existing_report = pyperclip.paste()
            break
        except Exception:
            time.sleep(0.2)
    else:
        existing_report = ""
    title = existing_report.splitlines()[0].strip() if existing_report.strip() else ""
    if title:
        print(f"Title: {title}")
    else:
        print("Title: not found")

    # Crop black borders and save ready-to-send image
    xray_img = Image.open(region1_path)
    xray_img = crop_black_borders(xray_img)
    xray_ready_path = os.path.join(screenshots_dir, "xray_ready_to_send.png")
    xray_img.save(xray_ready_path)
    print(f"Saved: {xray_ready_path}")

    with open(xray_ready_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    client = anthropic.Anthropic(api_key=load_api_key())
    print("\nGenerating radiology report...\n")

    report = ""
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        thinking={"type": "adaptive"},
        system=(
            "You are an expert radiologist writing ultra-concise ED reports. "
            "Use plain summary statements only. "
            "Never enumerate individual negative findings — if something is normal, say so in a single word or short phrase (e.g. 'Lungs clear', 'No fracture identified'). "
            "Only mention a structure if it is abnormal or directly relevant to the clinical question. "
            "Do not list what was not seen."
            "Do not comment on central venous catheters."
            "If the heart size is normal, say \"cardiomediastinal silhouette outlines normally\""
            "Do not comment on what projections were provided."
            "Unless you are very sure there is an abnormality, assume it is normal."
            "If you are reporting a pelvis or hip x-ray for query fracture use the report: No fracture or dislocation.  The pelvic viscera outline normally"
        ),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Clinical Information:\n{clinical_text}\n\n"
                            "Generate a brief radiology report."
                            "Use the headings CLINICAL INFORMATION and FINDINGS. Do not add * and # to delineate headings."
                            "ignore technical problems.  Ignore the abscence of a lateral projection."
                            "Write in short paragraphs."
                        ),
                    },
                ],
            }
        ],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            report += text

    print()

    if title:
        report = f"{title}\n\n{report}"

    # Save the report alongside the screenshots
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filepath = os.path.join(screenshots_dir, f"radiology_report_{timestamp}.txt")
    with open(report_filepath, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved: {report_filepath}")

    # Paste report into target window
    pyperclip.copy(report)
    pyautogui.click(-1114, 735)
    time.sleep(0.4)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")


if __name__ == "__main__":
    generate_radiology_report()
