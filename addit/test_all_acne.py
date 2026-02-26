import traceback
import sys
import os
sys.path.append('.')
from scripts.scoring import analyze_acne
import cv2

count = 0
errors = 0
for root, dirs, files in os.walk("data/ISD-198/Train/Acne_Vulgaris"):
    for file in files:
        if file.endswith(".jpg"):
            path = os.path.join(root, file)
            img = cv2.imread(path)
            img = cv2.resize(img, (512, 512))
            count += 1
            try:
                result = analyze_acne(img)
            except Exception as e:
                print(f"CRASH on {path}:")
                traceback.print_exc()
                errors += 1
                if errors > 2:
                    sys.exit(1)
print(f"Tested {count} images, {errors} errors")
