import argparse
import time

import pyautogui

from run_medgemma_report_flow import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MedGemma report flow in a loop.")
    parser.add_argument("-l", "--loops", type=int, required=True, help="Number of cases to process")
    parser.add_argument("-m", "--model", default="medgemma-4b-it", choices=["medgemma-4b-it", "medgemma-27b-it", "maira-2"], help="Model to use (default: medgemma-4b-it)")
    args = parser.parse_args()

    for i in range(1, args.loops + 1):
        print(f"\n--- Run {i}/{args.loops} ({args.model}) ---")
        try:
            run(model=args.model)
        except Exception as e:
            print(f"Error on run {i}: {e}")
            break
        if i < args.loops:
            pyautogui.press("f9")
            total = 8
            bar_width = 30
            for elapsed in range(total):
                remaining = total - elapsed
                filled = int(bar_width * elapsed / total)
                bar = "#" * filled + "-" * (bar_width - filled)
                print(f"\rWaiting for next case to download: [{bar}] {remaining}s ", end="", flush=True)
                time.sleep(1)
            print(f"\r{'Waiting for next case to download: done':<{bar_width + 45}}")

    print(f"\nCompleted {args.loops} run(s).")
