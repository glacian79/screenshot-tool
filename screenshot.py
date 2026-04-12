import os
from datetime import datetime
import numpy as np
from PIL import ImageGrab, Image


def grey_near_color(img, target_hex="009ccc", half=10, tolerance=10):
    """Turn grey any pixel matching target_hex and a box extending half pixels in each direction."""
    r = int(target_hex[0:2], 16)
    g = int(target_hex[2:4], 16)
    b = int(target_hex[4:6], 16)

    arr = np.array(img.convert("RGB"))
    diff = np.abs(arr.astype(int) - np.array([r, g, b]))
    mask = np.all(diff <= tolerance, axis=2)

    if not mask.any():
        return img

    h, w = mask.shape

    # Dilate the mask: OR-shift by every offset in [-half, half]
    dilated = mask.copy()
    for dy in range(-half, half + 1):
        src_r = slice(max(0, -dy), min(h, h - dy))
        dst_r = slice(max(0, dy), min(h, h + dy))
        for dx in range(-half, half + 1):
            if dy == 0 and dx == 0:
                continue
            src_c = slice(max(0, -dx), min(w, w - dx))
            dst_c = slice(max(0, dx), min(w, w + dx))
            dilated[dst_r, dst_c] |= mask[src_r, src_c]

    result = arr.copy()
    result[dilated] = [128, 128, 128]
    print(f"Greyed colour #{target_hex}: {int(dilated.sum())} pixels affected")
    return Image.fromarray(result)


def capture_and_save(timestamp=None):
    """Capture both screen regions, save as PNGs, and return (images, filepaths)."""
    # Create output folder in home directory
    home_dir = os.path.expanduser("~")
    output_dir = os.path.join(home_dir, "screenshots")
    os.makedirs(output_dir, exist_ok=True)

    # Regions defined as (left, top, right, bottom)
    # Region 2 uses negative x coordinates (monitor to the left of primary)
    regions = [
        (15, 282, 3458, 2076),        # Region 1: main area
        (-1964, 1132, -1328, 1822),   # Region 2: left monitor
        (50, 1100, 1500, 1600),      # Region 3: clinical information fallback
        (2320, 960, 3450, 1560),      # Region 4: clinical information fallback
    ]

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    max_width = 1024*2
    images = []
    filepaths = []

    for i, bbox in enumerate(regions, start=1):
        # all_screens=True is required to capture negative-coordinate monitors
        img = ImageGrab.grab(bbox=bbox, all_screens=True)

        # Resize proportionally if wider than max_width
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        # Grey out white areas and teal UI chrome across all regions
        img = grey_near_color(img, target_hex="ffffff")
        img = grey_near_color(img)

        filename = f"screenshot_{i}_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)
        img.save(filepath)
        print(f"Region {i} saved: {filepath}  ({img.width}x{img.height})")
        images.append(img)
        filepaths.append(filepath)

    return images, filepaths


if __name__ == "__main__":
    capture_and_save()
