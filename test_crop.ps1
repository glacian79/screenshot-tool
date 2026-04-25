param([string]$ImagePath)

if (-not $ImagePath) {
    Write-Host "Usage: .\test_crop.ps1 <image_path>"
    exit 1
}

python -c "
from PIL import Image
from screenshot import crop_black_borders
import sys

path = r'$ImagePath'
img = Image.open(path)
cropped = crop_black_borders(img)
out = path.rsplit('.', 1)[0] + '_cropped.png'
cropped.save(out)
print(f'Saved: {out}')
"
