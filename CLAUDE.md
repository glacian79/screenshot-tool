# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A two-script Python tool for capturing specific monitor regions as PNGs and optionally running OCR on them.

## Dependencies

- `Pillow` — screen capture and image resizing (`PIL.ImageGrab`, `PIL.Image`)
- `pytesseract` — OCR (wraps Tesseract; Tesseract must be installed separately on the system)

Install Python deps:
```bash
pip install Pillow pytesseract
```

## Running the scripts

Capture both screen regions to `~/screenshots/`:
```bash
python screenshot.py
```

Capture both regions and run OCR on region 2, saving a `.txt` file alongside the PNGs:
```bash
python ocr_screenshot.py
```

## Architecture

`screenshot.py` is the core module. Its `capture_and_save(timestamp=None)` function captures two hardcoded monitor regions (supporting negative-coordinate monitors via `all_screens=True`), resizes each to max 1024px wide, saves PNGs to `~/screenshots/`, and returns `(images, filepaths)`.

`ocr_screenshot.py` imports `capture_and_save` from `screenshot`, calls it with a shared timestamp, then runs `pytesseract.image_to_string` on the region 2 image and saves the result as a `.txt` file in the same output directory.

## Monitor regions

The two capture regions are defined in `screenshot.py` as `(left, top, right, bottom)` pixel coordinates:
- Region 1: `(15, 282, 3458, 2076)` — main monitor area
- Region 2: `(-1964, 1132, -1328, 1822)` — left monitor (negative x because it is left of the primary display)

These are hardcoded and must be updated if the monitor layout changes.
