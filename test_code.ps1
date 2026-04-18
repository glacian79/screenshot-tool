python -c "
from generate_report import capture_demographics
from screenshot import mask_color_for_ocr
from PIL import Image

capture_demographics()

img = Image.open('C:/Users/john.grieve/screenshots/demographics.png')
mask_color_for_ocr(img).save('C:/Users/john.grieve/screenshots/demographics_masked.png')
print('saved')
"
