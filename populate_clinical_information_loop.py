import ctypes
import msvcrt
import sys
import time

import pyautogui

from populate_clinical_information import populate_clinical_information
from rad_report_loop import mouse_scroll_down

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def focus_console():
    hwnd = kernel32.GetConsoleWindow()
    if hwnd:
        user32.SetForegroundWindow(hwnd)


def countdown_with_pause(seconds):
    focus_console()
    print("Check hanging protocol. Press space bar to pause.")
    end = time.time() + seconds
    while time.time() < end:
        if msvcrt.kbhit():
            if msvcrt.getch() == b' ':
                print("Paused. Press space bar to resume.")
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
            print(f"Usage: python populate_clinical_information_loop.py [count]")
            sys.exit(1)
    else:
        max_runs = None  # infinite

    runs = 0
    while max_runs is None or runs < max_runs:
        try:            
            # Move mouse to specified coordinates
            pyautogui.moveTo(3220, 1670, duration=0.1)  # duration=0.5 for smooth movement
            
            # Scroll down - negative value scrolls down
            # Approximately 5-10 clicks = half turn of scroll wheel
            mouse_scroll_down(6)  # number of clicks            
           
            countdown_with_pause(2)
            populate_clinical_information()
            runs += 1           

            if max_runs is None or runs < max_runs:
                pyautogui.press("f9") # save as draft.
                remaining = f"{max_runs - runs} remaining" if max_runs else "Ctrl+C to stop"
                print(f"\n{remaining}...")
                time.sleep(6)  # Wait for next images to hang

        except KeyboardInterrupt:
            print("\nStopped.")
            break

    if max_runs and runs >= max_runs:
        print(f"\nCompleted {runs} run(s).")
