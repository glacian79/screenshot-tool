import os
import re
import time

import anthropic
import pyautogui
import pyperclip
import pytesseract
from PIL import ImageEnhance, ImageGrab

from radiology_report import load_api_key

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\john.grieve\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Screen region containing sex/age, e.g. "[M] [006Y]"
DEMOG_REGION = (1200, 330, 3400, 540)

SYSTEM_PROMPT = (
    "You are a helpful assistant that improves radiology reports. "
    "Check this radiology report for errors and suggest improvements. "
    "Write a conclusion that relates back to the Clinical History without repeating findings in the body of the report. "
    "Use UK/Australian spelling.\n\n"
    "Assume elements of a normal report that are not mentioned are normal. "
    "Also add significant negatives relevant to the clinical history. "
    "Keep or Add a title"
    "Keep the headings \"HISTORY\", \"TECHNIQUE\", \"FINDINGS\", and \"CONCLUSION\", but otherwise write in paragraphs without headings. "
    "Please dont put ** around the headings.\n\n"
    "Do not repeat findings from the body of the report in the conclusion."
)


def capture_demographics():
    """OCR the demographics region and return (sex, age_str) or (None, None)."""
    img = ImageGrab.grab(bbox=DEMOG_REGION, all_screens=True)

    # Upscale for better OCR accuracy
    scale = 3
    img = img.resize((img.width * scale, img.height * scale))

    # Enhance contrast for bright text on dark background
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(2.0)

    # Save debug screenshot
    screenshots_dir = os.path.join(os.path.expanduser("~"), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    img.save(os.path.join(screenshots_dir, "demographics.png"))

    # PSM 6 = assume uniform block of text (better for multiline)
    # PSM 7 = single line only — wrong for this layout
    config = "--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]()| ^abcdefghijklmnopqrstuvwxyz"
    text = pytesseract.image_to_string(img, config=config)
    
    print(f"Demographics OCR raw:\n{text}")

    # Normalise common OCR misreads of brackets and digits
    text = text.replace("(", "[").replace(")", "]").replace("L", "[").replace("|", "I").replace("O", "0").replace("o", "0")

    # Match sex — [F] or [M]; brackets already normalised to [] by this point
    sex_match = re.search(
        r'\[([MF])\]',
        text,
        re.IGNORECASE
    )

    # Match age — handles: [005Y], [06M], [003D], [025W], leading zeros
    # Also handles space between digits and unit e.g. [005 Y]
    age_match = re.search(
        r'[\[\(](\d{1,3}\s*[DWMY])[\]\)]',
        text,
        re.IGNORECASE
    )

    # Match name — LASTNAME^FIRSTNAME pattern
    name_match = re.search(
        r'([A-Z]{2,}\^[A-Z]{2,})',
        text,
        re.IGNORECASE
    )

    # Match date — 18 Aug 2020 style
    date_match = re.search(
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})',
        text,
        re.IGNORECASE
    )

    sex = sex_match.group(1).upper() if sex_match else None
    age_raw = age_match.group(1).replace(" ", "").upper() if age_match else None
    name = name_match.group(1).upper() if name_match else None
    date = date_match.group(1) if date_match else None

    print(f"Parsed: Sex={sex}, Age={age_raw}, Name={name}, Date={date}")

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

    # Insert immediately after "HISTORY:" (with optional whitespace/newline)
    injected = re.sub(
        r'(HISTORY\s*:[ \t]*\n?)',
        lambda m: m.group(0) + demo_str + ". ",
        report_text,
        count=1,
        flags=re.IGNORECASE,
    )

    if injected == report_text:
        # No HISTORY heading found — prepend as a note
        injected = f"Patient: {demo_str}\n\n{report_text}"

    return injected


def improve_report():
    # Capture demographics before touching the report field
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

    # Click into the report field and copy all text
    pyautogui.click(-1070, 735)
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.3)

    report_text = pyperclip.paste()
    if not report_text.strip():
        print("Clipboard is empty — nothing to improve.")
        return

    report_text = inject_demographics(report_text, sex, age_raw)

    print("Improving report...\n")

    client = anthropic.Anthropic(api_key=load_api_key())

    improved = ""
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": report_text}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            improved += text

    print()

    # Save transcript of what was sent and received
    from datetime import datetime
    screenshots_dir = os.path.join(os.path.expanduser("~"), "screenshots")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    transcript_path = os.path.join(screenshots_dir, f"improve_report_{timestamp}.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write("=== SENT ===\n\n")
        f.write(report_text)
        f.write("\n\n=== RECEIVED ===\n\n")
        f.write(improved)
    print(f"Transcript saved: {transcript_path}")

    # Paste improved report back into the field
    pyperclip.copy(improved)
    pyautogui.click(-1070, 735)
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")


if __name__ == "__main__":
    improve_report()
