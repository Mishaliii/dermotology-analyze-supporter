import cv2
import glob
from ultralytics import FastSAM
import numpy as np

print("Loading FastSAM model...")
# Downloads fastsam-s.pt automatically
model = FastSAM('FastSAM-s.pt')

test_images = glob.glob("data/ISD-198/Train/8. Psoriasis pictures/*.jpg")[:2] + glob.glob("data/ISD-198/Train/110. Acne and Rosacea Photos/*.jpg")[:2]

for img_path in test_images:
    image_cv = cv2.imread(img_path)
    if image_cv is None: continue
    
    print(f"\n--- Segmentation for {img_path} ---")
    
    # Run FastSAM with everything mode
    results = model(image_cv, device='cpu', retina_masks=True, imgsz=640, conf=0.4, iou=0.9)
    
    for r in results:
        # masks is a list of boolean tensors (N, H, W)
        if r.masks is not None:
            mask_data = r.masks.data.cpu().numpy()
            print(f"Detected {len(mask_data)} distinct segmentations.")
            
            # Compute roughly how much of the image is covered by each mask
            h, w = mask_data.shape[1], mask_data.shape[2]
            total_pixels = h * w
            
            for i, mask in enumerate(mask_data):
                coverage = np.sum(mask) / total_pixels * 100
                if coverage > 5.0: # Only print significant masks
                    print(f"  Mask {i}: {coverage:.1f}% coverage")
        else:
            print("No masks found.")
