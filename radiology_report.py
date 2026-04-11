import base64
import glob
import os

import anthropic

from ocr_screenshot import capture_and_ocr


def generate_radiology_report():
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

    # Encode region 1 image as base64
    with open(region1_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    client = anthropic.Anthropic()
    print("\nGenerating radiology report...\n")

    report = ""
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=(
            "You are an expert radiologist. "
            "Generate concise, structured radiology reports based on the image and clinical information provided."
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
                            "Please generate a brief radiology report for this image using the clinical information provided."
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

    # Save the report alongside the screenshots
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filepath = os.path.join(screenshots_dir, f"radiology_report_{timestamp}.txt")
    with open(report_filepath, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved: {report_filepath}")


if __name__ == "__main__":
    generate_radiology_report()
