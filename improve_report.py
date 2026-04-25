import time
import os
import anthropic
import pyautogui
import pyperclip

from generate_report import (
    capture_demographics,
    format_age,
    inject_demographics,
    load_api_key,
)

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
    pyautogui.click(-870, 960)
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
    pyautogui.click(-870, 960)
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")


if __name__ == "__main__":
    improve_report()
