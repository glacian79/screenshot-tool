import os
from datetime import datetime
from PIL import ImageGrab, Image


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
    ]

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    max_width = 1024
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

        filename = f"screenshot_{i}_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)
        img.save(filepath)
        print(f"Region {i} saved: {filepath}  ({img.width}x{img.height})")
        images.append(img)
        filepaths.append(filepath)

    return images, filepaths


if __name__ == "__main__":
    capture_and_save()
