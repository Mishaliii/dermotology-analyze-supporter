import traceback
import sys
sys.path.append('.')
from scripts.scoring import get_visual_score

try:
    image_path = "data/ISD-198/Train/Acne_Vulgaris/046542VB.jpg" 
            
    print(f"Testing on {image_path}")
    result = get_visual_score(image_path, "Acne")
    print("\n--- OUTPUT ---")
    for k, v in result.items():
        if k == 'raw_features':
            print("raw_features:")
            for rk, rv in v.items():
                print(f"  {rk}: {rv}")
        elif k != 'sam_polygons':
            print(f"{k}: {v}")
except Exception as e:
    print("\n--- EXCEPTION ---")
    traceback.print_exc()
