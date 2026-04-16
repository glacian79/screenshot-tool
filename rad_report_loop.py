import glob
import os
import time

import pyautogui

from radiology_report import generate_radiology_report

SCREENSHOTS_DIR = os.path.join(os.path.expanduser("~"), "screenshots")


if __name__ == "__main__":
    while True:
        try:
            before = set(glob.glob(os.path.join(SCREENSHOTS_DIR, "radiology_report_*.txt")))

            generate_radiology_report()

            after = set(glob.glob(os.path.join(SCREENSHOTS_DIR, "radiology_report_*.txt")))
            if not (after - before):
                print("No clinical information found — stopping.")
                break

            pyautogui.press("f9")
            print("\nPress Ctrl+C to stop...")
            time.sleep(10)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
