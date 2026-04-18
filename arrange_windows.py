import ctypes
import time

import pygetwindow as gw

user32 = ctypes.windll.user32

# Monitor layout (logical pixels, DPI-scaled)
# Main monitor:  left=0,     top=0,   width=3840, height=2160
# Left monitor:  left=-3440, top=718, width=3440, height=1440

MAIN_LEFT   = 0
MAIN_TOP    = 0
MAIN_W      = 3840
MAIN_H      = 2160

LEFT_LEFT   = -3440
LEFT_TOP    = 718
LEFT_W      = 3440
LEFT_H      = 1390

third = LEFT_W // 3  # 1146

# Middle third of left monitor
CHROME_LEFT = LEFT_LEFT + third
CHROME_W    = third + 1  # 1147 — absorbs rounding

# Right third of left monitor
PS_LEFT     = LEFT_LEFT + 2 * third + 1
PS_W        = LEFT_W - (2 * third + 1)  # reaches exactly x=0


def move(win, left, top, width, height):
    win.restore()
    time.sleep(0.15)
    win.moveTo(left, top)
    win.resizeTo(width, height)
    # Bring to front without stealing keyboard focus from the active window
    #hwnd = win._hWnd
    #user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_TOPMOST, SWP_NOMOVE|SWP_NOSIZE
    #user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_NOTOPMOST (removes always-on-top but keeps raised)


def arrange():
    moved = []

    for w in gw.getAllWindows():
        t = w.title
        if not t:
            continue

       # if "InteleViewer" in t and "Search Tool" not in t:
       #     move(w, MAIN_LEFT, MAIN_TOP, MAIN_W, MAIN_H)
       #     moved.append(f"IntelliViewer -> main fullscreen: {t[:60]}")

        elif "Google Chrome" in t:
            move(w, CHROME_LEFT, LEFT_TOP, CHROME_W, LEFT_H + 5)
            moved.append(f"Chrome -> left middle third: {t[:60]}")

        elif t == "PowerScribe One":
            move(w, PS_LEFT, LEFT_TOP, PS_W, LEFT_H)
            moved.append(f"PowerScribe -> left right third: {t[:60]}")

        elif "Notepad++" in t:
            w.minimize()
            moved.append(f"Notepad++ -> minimized: {t[:60]}")

    if moved:
        for m in moved:
            print(m)
    else:
        print("No target windows found.")


if __name__ == "__main__":
    arrange()
