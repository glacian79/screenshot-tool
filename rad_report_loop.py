import glob
import msvcrt
import os
import sys
import time

import pyautogui

from generate_report import generate_radiology_report

SCREENSHOTS_DIR = os.path.join(os.path.expanduser("~"), "screenshots")


def countdown_with_pause(seconds):
    print("check hanging protocol. press space bar to pause")
    end = time.time() + seconds
    while time.time() < end:
        if msvcrt.kbhit():
            if msvcrt.getch() == b' ':
                print("press space bar to resume")
                while True:
                    if msvcrt.kbhit() and msvcrt.getch() == b' ':
                        break
                    time.sleep(0.05)
                end = time.time() + (end - time.time())
        time.sleep(0.05)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            max_runs = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python rad_report_loop.py [count]")
            sys.exit(1)
    else:
        max_runs = None  # infinite

    runs = 0
    while max_runs is None or runs < max_runs:
        try:
            before = set(glob.glob(os.path.join(SCREENSHOTS_DIR, "radiology_report_*.txt")))

            countdown_with_pause(6)
            generate_radiology_report()
            runs += 1

            after = set(glob.glob(os.path.join(SCREENSHOTS_DIR, "radiology_report_*.txt")))
            if not (after - before):
                print("No clinical information found — stopping.")
                break

            if max_runs is None or runs < max_runs:
                pyautogui.press("f9")
                remaining = f"{max_runs - runs} remaining" if max_runs else "Ctrl+C to stop"
                print(f"\n{remaining}...")
                #time.sleep(10)  # not needed if the hanging protocol check is implemented.

        except KeyboardInterrupt:
            print("\nStopped.")
            break

    if max_runs and runs >= max_runs:
        print(f"\nCompleted {runs} run(s).")
