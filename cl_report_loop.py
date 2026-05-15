import sys
import time

import pyautogui

from generate_report import generate_radiology_report

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python rad_report_loop.py <count>")
        sys.exit(1)
    try:
        count = int(sys.argv[1])
    except ValueError:
        print("Error: count must be an integer")
        sys.exit(1)

    for i in range(1, count + 1):
        print(f"\n--- Run {i}/{count} ---")
        try:
            generate_radiology_report()
        except Exception as e:
            print(f"Error on run {i}: {e}")
            break
        if i < count:
            pyautogui.press("f9")
            total = 4
            bar_width = 30
            for elapsed in range(total):
                remaining = total - elapsed
                filled = int(bar_width * elapsed / total)
                bar = "#" * filled + "-" * (bar_width - filled)
                print(f"\rWaiting for next case to download: [{bar}] {remaining}s ", end="", flush=True)
                time.sleep(1)
            print(f"\r{'Waiting for next case to download: done':<{bar_width + 45}}")

    print(f"\nCompleted {count} run(s).")
