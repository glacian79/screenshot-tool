import os
import re
from datetime import datetime

import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\john.grieve\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

from screenshot import capture_and_save


def capture_and_ocr():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Capture both regions using shared timestamp so filenames align
    images, filepaths = capture_and_save(timestamp=timestamp)

    # Run OCR on region 2 (index 1)
    region2_img = images[1]
    text = pytesseract.image_to_string(region2_img)

    # Save extracted text alongside the screenshots
    output_dir = os.path.dirname(filepaths[1])
    txt_filename = f"ocr_region2_{timestamp}.txt"
    txt_filepath = os.path.join(output_dir, txt_filename)

    with open(txt_filepath, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"OCR text saved: {txt_filepath}")

    # Extract text between "Relevant" and "IMAGING"
    match = re.search(r"Relevant(.*?)IMAGING", text, re.DOTALL | re.IGNORECASE)
    if match:
        clinical_text = match.group(1).strip()
        clinical_filepath = os.path.join(output_dir, "clinicalInformation.txt")
        with open(clinical_filepath, "w", encoding="utf-8") as f:
            f.write(clinical_text)
        print(f"Clinical information saved: {clinical_filepath}")
    else:
        print("No text found between 'Relevant' and 'IMAGING'")


if __name__ == "__main__":
    capture_and_ocr()
