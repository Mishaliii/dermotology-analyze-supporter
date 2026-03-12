import cv2
import numpy as np

def test_logic():
    # Simulate a 1000x1000 patch of skin
    img = np.zeros((1000, 1000, 3), dtype=np.uint8)
    img[:, :] = (150, 150, 200) # skin color (BGR roughly)
    
    # Add 12 "pimples" (Severity 2-3)
    pimples = [(100,100), (200,150), (150,300), (500,500), (600,600), 
               (800,100), (900,200), (100,900), (200,800), (500,800),
               (600,200), (700,700)]
               
    for p in pimples:
        cv2.circle(img, p, 8, (0, 0, 200), -1) # Red pimple
        
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0, 30, 50]), np.array([15, 255, 255]))
    mask2 = cv2.inRange(hsv, np.array([160, 30, 50]), np.array([180, 255, 255]))
    red_mask = mask1 + mask2
    
    # Assume the whole thing is skin for test purposes
    skin = np.ones_like(red_mask) * 255
    
    # 1. Without morphology
    comps_raw = cv2.connectedComponents(red_mask)[0] - 1
    
    # 2. With our current morphology (Ellipse 5x5)
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    smooth5 = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, k5)
    comps_5 = cv2.connectedComponents(smooth5)[0] - 1
    
    # 3. With a stronger morphology (Ellipse 15x15)
    k15 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15,15))
    smooth15 = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, k15)
    comps_15 = cv2.connectedComponents(smooth15)[0] - 1
    
    cov = np.sum(red_mask > 0) / 1000000.0
    
    print(f"Goal: {len(pimples)} Pimples")
    print(f"Raw detected: {comps_raw}")
    print(f"With 5x5 smoothing: {comps_5}")
    print(f"With 15x15 smoothing: {comps_15}")
    print(f"Coverage: {cov:.6f}")

if __name__ == "__main__":
    test_logic()
