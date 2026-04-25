import base64
import json
import os
import re
import time
from datetime import datetime

import anthropic
import pyautogui
import pyperclip

from capture_workflow import run_capture_workflow
from check_priors import check_priors

KEY_PATH = r"C:\Users\john.grieve\.claude\API_KEYS\reportgenerator.key"


def load_api_key():
    with open(KEY_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


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


def find_matching_prior(title):
    """Search prior*.txt files for the one whose first all-caps line matches title."""
    if not title:
        return None
    screenshots_dir = os.path.join(os.path.expanduser("~"), "screenshots")
    import glob as _glob
    prior_files = sorted(_glob.glob(os.path.join(screenshots_dir, "prior*.txt")))
    for path in prior_files:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        for line in text.splitlines():
            line = line.strip()
            if line and line == line.upper() and any(c.isalpha() for c in line):
                if line.upper() == title.upper():
                    print(f"Matching prior found: {os.path.basename(path)} — '{line}'")
                    return text
                break  # only check the first all-caps line per file
    print("No matching prior found")
    return None


def _is_mostly_white(path, threshold=220, white_fraction=0.75):
    """Return True if more than white_fraction of pixels are brighter than threshold."""
    from PIL import Image as _Image
    img = _Image.open(path).convert("L")
    pixels = img.getdata()
    white = sum(1 for p in pixels if p > threshold)
    return white / len(pixels) > white_fraction


def generate_radiology_report():
    screenshots_dir = os.path.join(os.path.expanduser("~"), "screenshots")
    xray_paths, clinical_text, sex, age_raw = run_capture_workflow()

    if sex or age_raw:
        parts = []
        if sex:
            parts.append("Male" if sex == "M" else "Female")
        if age_raw:
            parts.append(format_age(age_raw))
        demo_str = ", ".join(parts)
        print(f"Demographics: {demo_str}")
        clinical_text = demo_str + ". " + (clinical_text or "")
    else:
        print("Demographics: not found")

    if not clinical_text or not clinical_text.strip():
        print("No clinical information found")
        return

    if not xray_paths:
        print("No xray images found")
        return

    # Extract title from existing report (first line)
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

    check_priors()
    prior_text = find_matching_prior(title)

    # Filter out mostly-white images (scanned request forms)
    filtered_paths = []
    for path in xray_paths:
        if _is_mostly_white(path):
            request_path = os.path.join(screenshots_dir, "request.png")
            os.replace(path, request_path)
            print(f"{os.path.basename(path)} is mostly white — renamed to request.png")
        else:
            filtered_paths.append(path)
    xray_paths = filtered_paths

    if not xray_paths:
        print("No xray images remain after filtering")
        return

    # Build content: one image block per xray, then the text prompt
    content = []
    for path in xray_paths:
        with open(path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_data,
            },
        })
    prior_section = f"Prior report:\n{prior_text}\n\n" if prior_text else ""
    llm_text = (
        f"{prior_section}"
        f"Clinical Information:\n{clinical_text}\n\n"
        "Generate a brief radiology report."
        "Use the headings CLINICAL INFORMATION and FINDINGS. Do not add * and # to delineate headings."
        "ignore technical problems.  Ignore the abscence of a lateral projection."
        "Write in short paragraphs."
    )
    content.append({"type": "text", "text": llm_text})

    model       = "claude-opus-4-6"
    max_tokens  = 1024
    thinking    = {"type": "adaptive"}
    system      = (
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
        "If a prior report is provided and is the same type of examination, begin the FINDINGS section with 'Images are compared with the prior examination on [date from prior].' "
        "If no prior report is provided, or it is not the same type of examination, begin the FINDINGS section with 'No prior x-rays available for comparison.'"
    )

    # Save full request for inspection (images replaced with filename placeholders)
    content_log = [
        {"type": "image", "file": os.path.basename(p)} for p in xray_paths
    ] + [{"type": "text", "text": llm_text}]
    request_log = {
        "model": model,
        "max_tokens": max_tokens,
        "thinking": thinking,
        "system": system,
        "messages": [{"role": "user", "content": content_log}],
    }
    with open(os.path.join(screenshots_dir, "llm_request.json"), "w", encoding="utf-8") as f:
        json.dump(request_log, f, indent=2)

    client = anthropic.Anthropic(api_key=load_api_key())
    print("\nGenerating radiology report...\n")

    report = ""
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        thinking=thinking,
        system=system,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            report += text

    print()

    if title:
        report = f"{title}\n\n{report}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save report then move everything into a timestamped subfolder
    report_filepath = os.path.join(screenshots_dir, f"radiology_report_{timestamp}.txt")
    with open(report_filepath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved: {report_filepath}")

    archive_dir = os.path.join(screenshots_dir, "archive", timestamp)
    os.makedirs(archive_dir, exist_ok=True)
    for fname in os.listdir(screenshots_dir):
        src = os.path.join(screenshots_dir, fname)
        if os.path.isfile(src):
            os.replace(src, os.path.join(archive_dir, fname))
    print(f"Files archived to: {archive_dir}")

    pyperclip.copy(report)
    pyautogui.click(-1114, 735)
    time.sleep(0.4)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")


if __name__ == "__main__":
    generate_radiology_report()
