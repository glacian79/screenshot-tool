import os
import re
import time
from datetime import datetime

import anthropic
import pyautogui
import pyperclip

from check_priors import check_priors
from generate_report import find_matching_prior, load_api_key
from medgemma_report import run_medgemma_report

SCREENSHOTS_DIR = os.path.join(os.path.expanduser("~"), "screenshots")


def run(model=None):
    # Step 1: Read title from PowerScribe before capturing
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
    print(f"Title: {title}" if title else "Title: not found")

    # Step 2: Run MedGemma — captures images, OCRs demographics/clinical text, returns findings
    mg_findings = run_medgemma_report(title=title, model=model)
    if not mg_findings or mg_findings.startswith("Error"):
        print("MedGemma did not return usable findings. Aborting.")
        return

    # Step 3: Capture and find matching prior
    check_priors()
    prior_text = find_matching_prior(title)
    prior_section = f"Prior report:\n{prior_text}\n\n" if prior_text else ""

    # Step 4: Send MedGemma findings to Claude for formatting
    clinical_file = os.path.join(SCREENSHOTS_DIR, "clinicalInformation.txt")
    clinical_info = ""
    if os.path.exists(clinical_file):
        clinical_info = open(clinical_file, encoding="utf-8").read().strip()
    clinical_section = f"Clinical information:\n{clinical_info}\n\n" if clinical_info else ""

    llm_text = (
        f"{prior_section}"
        f"{clinical_section}"
        f"MedGemma findings:\n{mg_findings}\n\n"
        "Using the findings above, generate a brief radiology report. "
        "Use Australian/British spelling. "
        "Use the headings CLINICAL INFORMATION and FINDINGS. Do not add * and # to delineate headings. "
        "Begin CLINICAL INFORMATION with the patients sex and age if known"
        "Write in short paragraphs."
        "Keep sentences short, even if it means they are not technically grammatically corrent."
        "Do not write a SUMMARY paragraph for plain films"
    )

    system = (
        "You are an expert radiologist writing ultra-concise ED reports. "        
    )

    client = anthropic.Anthropic(api_key=load_api_key())
    print("\nRefining report with Claude...\n")

    report = ""
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": llm_text}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            report += text

    print()

    if title:
        report = f"{title}\n\n{report}"

    # Step 5: Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filepath = os.path.join(SCREENSHOTS_DIR, f"radiology_report_{timestamp}.txt")
    with open(report_filepath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved: {report_filepath}")

    # Step 6: Archive screenshots
    safe_title = re.sub(r'[\\/:*?"<>|]', '', title).strip() if title else ""
    archive_name = f"{timestamp}_{safe_title}" if safe_title else timestamp
    archive_dir = os.path.join(SCREENSHOTS_DIR, "archive", archive_name)
    os.makedirs(archive_dir, exist_ok=True)
    for fname in os.listdir(SCREENSHOTS_DIR):
        src = os.path.join(SCREENSHOTS_DIR, fname)
        if os.path.isfile(src):
            os.replace(src, os.path.join(archive_dir, fname))
    print(f"Files archived to: {archive_dir}")

    # Step 7: Paste into PowerScribe
    pyperclip.copy(report)
    pyautogui.click(-1114, 735)
    time.sleep(0.4)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")


if __name__ == "__main__":
    run()
