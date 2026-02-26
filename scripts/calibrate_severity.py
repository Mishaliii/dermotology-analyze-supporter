import os
import cv2
import json
import numpy as np
from tqdm import tqdm
import scoring

DATA_DIR = "data/ISD-198"
CALIBRATION_FILE = "calibration.json"

def calibrate():
    print("Starting Severity Calibration over dataset...")
    
    raw_acne_scores = []
    raw_pso_scores = []
    
    # We will compute raw severity for acne and psoriasis metrics
    
    valid_extensions = {".jpg", ".jpeg", ".png"}
    count = 0
    max_images = 500 # Don't run on too many for speed, sample size of 500 is statistically significant
    
    for root, _, files in os.walk(DATA_DIR):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_extensions:
                path = os.path.join(root, f)
                img = cv2.imread(path)
                if img is None: continue
                
                # Resize for speed like in pipeline
                img = cv2.resize(img, (224, 224))
                
                # We analyze generic features for both to build a distribution
                try:
                    # Acne raw score distribution
                    acne_res = scoring.analyze_acne(img)
                    raw_acne = acne_res["raw_features"]["morphology_score"] * 0.25 + \
                               acne_res["raw_features"]["coverage"] * 10 * 0.3 + \
                               (acne_res["raw_features"]["hybrid_density"] / 40.0) * 0.35 + \
                               acne_res["raw_features"]["redness_norm"] * 0.1
                    raw_acne_scores.append(raw_acne)
                    
                    # Psoriasis raw features (erythema, scaling, thickness)
                    pso_res = scoring.analyze_psoriasis(img)
                    raw_pso = pso_res["raw_features"]
                    raw_pso_scores.append({
                        "redness": raw_pso["redness_norm"],
                        "texture": raw_pso["texture_norm"],
                        "elevation": raw_pso["elevation_norm"]
                    })
                except Exception as e:
                    print(f"Error processing {path}: {e}")
                
                count += 1
                if count >= max_images:
                    break
        if count >= max_images:
            break
            
    print(f"Processed {count} images.")
    
    # Compute percentiles
    def get_percentiles(scores):
        if not scores: return [0.5, 1.0, 2.0]
        return np.percentile(scores, [30, 60, 85]).tolist()
        
    acne_p = get_percentiles(raw_acne_scores)
    
    red_scores = [x["redness"] for x in raw_pso_scores]
    tex_scores = [x["texture"] for x in raw_pso_scores]
    ele_scores = [x["elevation"] for x in raw_pso_scores]
    
    pso_red_p = get_percentiles(red_scores)
    pso_tex_p = get_percentiles(tex_scores)
    pso_ele_p = get_percentiles(ele_scores)
    
    calibration = {
        "acne_raw_severity": acne_p,
        "psoriasis_redness": pso_red_p,
        "psoriasis_texture": pso_tex_p,
        "psoriasis_elevation": pso_ele_p,
        "metadata": {
            "num_images_calibrated": count,
            "percentiles_used": [30, 60, 85]
        }
    }
    
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(calibration, f, indent=4)
        
    print(f"Calibration complete! Saved to {CALIBRATION_FILE}")
    print(json.dumps(calibration, indent=2))

if __name__ == "__main__":
    calibrate()
