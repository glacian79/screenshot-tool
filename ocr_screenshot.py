import base64
import os
import re
from datetime import datetime

import anthropic
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\john.grieve\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

KEY_PATH = r"C:\Users\john.grieve\.claude\API_KEYS\reportgenerator.key"

from arrange_windows import arrange
from screenshot import capture_and_save


def load_api_key():
    with open(KEY_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def capture_and_ocr():
    arrange()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Capture all regions using shared timestamp so filenames align
    images, filepaths = capture_and_save(timestamp=timestamp)

    output_dir = os.path.dirname(filepaths[1])

    # Run OCR on region 2 first; fall back to region 3 then region 4 if no text found.
    # Track the region with the most text across all attempts for the Claude fallback.
    source = None
    best_index, best_label, best_text = 1, "region2", ""

    for region_index, label in [(1, "region2"), (2, "region3"), (3, "region4"), (4, "region5")]:
        text = pytesseract.image_to_string(images[region_index])

        txt_filepath = os.path.join(output_dir, f"ocr_{label}_{timestamp}.txt")
        with open(txt_filepath, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"OCR text saved: {txt_filepath}")

        if len(text.strip()) > len(best_text.strip()):
            best_index, best_label, best_text = region_index, label, text

        if text.strip():
            source = label
            break

        next_regions = {"region2": "region3", "region3": "region4", "region4": "region5"}
        if label in next_regions:
            print(f"No text found in {label}, trying {next_regions[label]}...")

    # Extract clinical information using region-appropriate delimiters
    match = None
    if source == "region5":
        match = re.search(r"Relevant(.*?)\n\n", best_text, re.DOTALL | re.IGNORECASE)
    elif source in ("region2", "region3", "region4"):
        best_text = re.sub(r"(?i)(?<=order/details:)\n\n", " ", best_text)
        with open(os.path.join(output_dir, f"ocr_{best_label}_{timestamp}.txt"), "w", encoding="utf-8") as f:
            f.write(best_text)
        match = re.search(r"order/details:(.*?)\n\n", best_text, re.DOTALL | re.IGNORECASE)

    if match:
        clinical_text = match.group(1).strip()
        clinical_filepath = os.path.join(output_dir, "clinicalInformation.txt")
        with open(clinical_filepath, "w", encoding="utf-8") as f:
            f.write(clinical_text)
        print(f"Clinical information saved: {clinical_filepath}")
        return

    # Final fallback: ask Claude to extract clinical information from the region with most text
    if best_text.strip():
        print(f"No clinical information found via OCR — sending {best_label} image to Claude...")
        with open(filepaths[best_index], "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        client = anthropic.Anthropic(api_key=load_api_key())
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            messages=[{
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
                    {"type": "text", "text": "Extract clinical information text from this image."},
                ],
            }],
        )
        clinical_text = next(b.text for b in response.content if b.type == "text")
        clinical_filepath = os.path.join(output_dir, "clinicalInformation.txt")
        with open(clinical_filepath, "w", encoding="utf-8") as f:
            f.write(clinical_text)
        print(f"Clinical information saved (via Claude): {clinical_filepath}")
    else:
        print("No clinical information found")


if __name__ == "__main__":
    capture_and_ocr()
