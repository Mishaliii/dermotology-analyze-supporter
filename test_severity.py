import cv2
import sys
import glob

sys.path.append('scripts')
from pipeline import analyze_skin_image

def test_scoring():
    files = glob.glob('data/**/*.jpg', recursive=True)
    if not files:
        print("No test images found in dataset.")
        return

    # test a few images
    for test_img in files[:3]:
        print(f"\n--- Testing on image: {test_img} ---")
        img_cv = cv2.imread(test_img)
        
        if img_cv is None:
            print("Failed to load image.")
            continue
            
        res = analyze_skin_image(img_cv)
        
        print(f"Top Condition: {res['top_condition']}")
        
        if "severity" in res:
            sev = res["severity"]
            print(f"Global Grade: {sev['max_severity_grade']}")
            print(f"Raw Features: {sev['raw_features']}")
            
            print("Regional:")
            for r, s in sev['regional_scores'].items():
                print(f"  {r}: {s}")
                
if __name__ == "__main__":
    test_scoring()
