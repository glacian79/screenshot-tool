"""
Background listener — triggers radiology_report.py when the dictaphone A button is pressed.
Set TRIGGER_KEY below to the key name printed by detect_key.py.
Run this script once; it stays running in the background.
"""
import subprocess
import sys

import keyboard

TRIGGER_KEY = "a"  # replace with the key name from detect_key.py

print(f"Listening for '{TRIGGER_KEY}' key — press it to generate a report. Ctrl+C to quit.")

def run_report():
    print("Triggered — running radiology_report.py...")
    subprocess.Popen([sys.executable, "radiology_report.py"])

keyboard.add_hotkey(TRIGGER_KEY, run_report, suppress=True)
keyboard.wait()
