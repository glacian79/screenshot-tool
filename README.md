# Screenshot Radiology Report Tool

Captures defined screen regions, extracts clinical information via OCR, and generates a structured radiology report using the Claude API. The report is streamed to the terminal, saved to disk, and pasted into a target window automatically.

## How it works

1. **`screenshot.py`** captures two screen regions and saves them as resized PNGs to `~/screenshots/`
2. **`ocr_screenshot.py`** runs Tesseract OCR on region 2 and extracts the text between `Relevant` and `IMAGING` into `clinicalInformation.txt`
3. **`radiology_report.py`** sends the region 1 image and clinical information to Claude Opus, streams the report to the terminal, saves it, and pastes it into a target window
4. **`listener.py`** runs in the background and triggers `radiology_report.py` when a configured hotkey (e.g. a dictaphone button) is pressed

## Requirements

### System dependencies

- **Python 3.10+**
- **Tesseract OCR** — install via winget:
  ```
  winget install UB-Mannheim.TesseractOCR
  ```
  Installed to `C:\Users\<user>\AppData\Local\Programs\Tesseract-OCR\` by default.

### Python dependencies

```
pip install Pillow pytesseract anthropic pyautogui pyperclip keyboard
```

| Package | Purpose |
|---|---|
| `Pillow` | Screen capture and image resizing |
| `pytesseract` | Python wrapper for Tesseract OCR |
| `anthropic` | Claude API SDK |
| `pyautogui` | Mouse click and keyboard automation |
| `pyperclip` | Clipboard access |
| `keyboard` | Global hotkey listener |

### Anthropic API key

Store your API key in a plain text file:
```
C:\Users\<user>\.claude\API_KEYS\reportgenerator.key
```

## Usage

### Generate a report manually

```
python radiology_report.py
```

### Trigger via a hardware button (e.g. dictaphone)

First identify the key your button sends:
```
python detect_key.py
```
Press the button, then Ctrl+C. Update `TRIGGER_KEY` in `listener.py` with the reported key name, then start the listener:
```
python listener.py
```

## Output

All output files are saved to `~/screenshots/`:

| File | Description |
|---|---|
| `screenshot_1_<timestamp>.png` | Region 1 — main monitor area (sent to Claude) |
| `screenshot_2_<timestamp>.png` | Region 2 — left monitor (used for OCR) |
| `ocr_region2_<timestamp>.txt` | Full OCR text from region 2 |
| `clinicalInformation.txt` | Extracted clinical information (overwritten each run) |
| `radiology_report_<timestamp>.txt` | Generated radiology report |

## Monitor regions

Capture coordinates are hardcoded in `screenshot.py` as `(left, top, right, bottom)`:

| Region | Coordinates | Description |
|---|---|---|
| 1 | `(15, 282, 3458, 2076)` | Main monitor area |
| 2 | `(-1964, 1132, -1328, 1822)` | Left monitor (negative x) |

Update these if your monitor layout changes.
