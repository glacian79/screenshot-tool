"""Run this script, press the button on your dictaphone, then Ctrl+C to exit."""
import keyboard

print("Press the button on your dictaphone (Ctrl+C to quit)...")

keyboard.start_recording()

try:
    keyboard.wait()
except KeyboardInterrupt:
    events = keyboard.stop_recording()
    for e in events:
        if e.event_type == "down":
            print(f"Key detected: name='{e.name}'  scan_code={e.scan_code}")
