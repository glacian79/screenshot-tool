import os
import sys
import time

import anthropic
import pyautogui
import pyperclip

from ocr_screenshot import capture_and_ocr, load_api_key


def populate_clinical_details():
    capture_and_ocr()

    screenshots_dir = os.path.join(os.path.expanduser("~"), "screenshots")
    clinical_filepath = os.path.join(screenshots_dir, "clinicalInformation.txt")

    if not os.path.exists(clinical_filepath):
        print("clinicalInformation.txt not found")
        return

    with open(clinical_filepath, "r", encoding="utf-8") as f:
        clinical_text = f.read().strip()
        # clinical_text = f"CLINICAL INFORMATION:\n{f.read().strip()}\n\nFINDINGS:\n"

    if not clinical_text:
        print("clinicalInformation.txt is empty")
        return

    client = anthropic.Anthropic(api_key=load_api_key())
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"Rewrite this text. Correct spelling and grammar. "
                       f"Remove all-caps if present. "
                       f"Return only the corrected text with no explanation:\n\n{clinical_text}",
        }],
    )
    corrected_text = next(b.text for b in response.content if b.type == "text")
    sys.stdout.buffer.write(f"\n{corrected_text}\n".encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()

    pyperclip.copy(corrected_text)
    pyautogui.click(-1114, 735)
    time.sleep(0.3)
    #pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.1)
    pyautogui.press("tab")


if __name__ == "__main__":
    populate_clinical_details()
