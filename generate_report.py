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


_MODALITY_WORDS = re.compile(r'\b(x-?ray|xray|cr|xr|right|left|bilateral|and|or|series|views?)\b', re.IGNORECASE)


def _title_keywords(text):
    """Strip modality words and return the remaining unique lowercase words (length >= 2)."""
    cleaned = _MODALITY_WORDS.sub('', text)
    return {w.lower() for w in re.split(r'\W+', cleaned) if len(w) >= 2}


def find_matching_prior(title):
    """Search prior*.txt files for the one whose first all-caps line shares any keyword with title."""
    if not title:
        return None
    current_keywords = _title_keywords(title)
    if not current_keywords:
        return None
    print(f"Matching priors — current title: '{title}' → keywords: {current_keywords}")
    screenshots_dir = os.path.join(os.path.expanduser("~"), "screenshots")
    import glob as _glob
    prior_files = sorted(_glob.glob(os.path.join(screenshots_dir, "prior*.txt")))
    for path in prior_files:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        date_match = re.search(r'Examination date:\s*(.+)', text)
        date_str = date_match.group(1).strip() if date_match else "unknown"
        print(f"  {os.path.basename(path)}: date={date_str}")
        title_match = re.search(r'Prior title:\s*(.+)', text)
        prior_title_line = title_match.group(1).strip() if title_match else ""
        prior_keywords = _title_keywords(prior_title_line)
        print(f"    Comparing: {current_keywords} vs {prior_keywords}  (prior title: '{prior_title_line}')")
        if current_keywords & prior_keywords:
            print(f"    Match found: {os.path.basename(path)}")
            return text
    print("No matching prior found")
    return None


def _is_mostly_white(path, threshold=220, white_fraction=0.75):
    """Return True if more than white_fraction of pixels are brighter than threshold."""
    from PIL import Image as _Image
    img = _Image.open(path).convert("L")
    pixels = img.get_flattened_data()
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
    prior_for_llm = re.sub(r'(Prior title:|Prior accession number:).*\n?', '', prior_text) if prior_text else None
    prior_section = f"Prior report:\n{prior_for_llm}\n\n" if prior_for_llm else ""
    llm_text = (
        f"{prior_section}"
        f"Clinical Information:\n{clinical_text}\n\n"
        "Generate a brief radiology report."
        "Use Australian/British spelling"
        "Use the headings CLINICAL INFORMATION and FINDINGS. Do not add * and # to delineate headings."
        "ignore technical problems.  Ignore the abscence of a lateral projection."
        "If multiple xrays are being reported in the one report separate the xrays under FINDINGS with Xray <body part>.  For example: X-ray Chest: <findings> \n\n X-ray hand: <findings>"
        "If the title referes to only a single region, do not add the region again under FINDINGS."
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
        "Do not comment on any line or catheter unless it was mentioned in the prior report."
        "If the heart size is normal, say \"cardiomediastinal silhouette outlines normally\""
        "Do not comment on what projections were provided."
        "Unless you are very sure there is an abnormality, assume it is normal."
        "Do not comment on how the ossifications centres correllate with age unless specifically instructed."
        "If you are reporting an abdomen x-ray, on the topic of faecal loading say: There is some faecal material in the colon, within normal limits."
        "If you are reporting a pelvis or hip x-ray for query fracture use the report: No fracture or dislocation.  The pelvic viscera outline normally"
        "If a prior report is provided and is the same type of examination, begin the FINDINGS section with 'Images are compared with the prior examination on [date from prior].\n\n' "
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

    safe_title = re.sub(r'[\\/:*?"<>|]', '', title).strip() if title else ""
    archive_name = f"{timestamp}_{safe_title}" if safe_title else timestamp
    archive_dir = os.path.join(screenshots_dir, "archive", archive_name)
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
