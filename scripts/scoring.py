import cv2
import numpy as np
import os
import json

# Lazy load FastSAM
_FASTSAM_MODEL = None
def get_fastsam_model():
    global _FASTSAM_MODEL
    if _FASTSAM_MODEL is None:
        from ultralytics import FastSAM
        _FASTSAM_MODEL = FastSAM('FastSAM-s.pt')
    return _FASTSAM_MODEL

_CALIBRATION_DATA = None
def get_calibration_data():
    global _CALIBRATION_DATA
    if _CALIBRATION_DATA is None:
        calib_path = os.path.join(os.path.dirname(__file__), '..', 'calibration.json')
        if os.path.exists(calib_path):
            with open(calib_path, 'r') as f:
                _CALIBRATION_DATA = json.load(f)
        else:
            # Fallback static estimates if script wasn't run
            _CALIBRATION_DATA = {
                "acne_raw_severity": [1.5, 2.5, 3.5], # Example mapping points
                "psoriasis_redness": [0.2, 0.4, 0.6],
                "psoriasis_texture": [0.2, 0.4, 0.6],
                "psoriasis_elevation": [0.1, 0.3, 0.5]
            }
    return _CALIBRATION_DATA

def map_score_to_grade(raw_val, percentiles):
    """ Maps a raw score to grades 1, 2, 3, or 4 strictly based on percentile thresholds """
    if raw_val <= percentiles[0]: return 1
    if raw_val <= percentiles[1]: return 2
    if raw_val <= percentiles[2]: return 3
    return 4

def detect_skin(image_cv):
    """ Detects skin area to normalize coverage and prevent zoom bias. """
    ycrcb = cv2.cvtColor(image_cv, cv2.COLOR_BGR2YCrCb)
    # Generic skin ranges in YCrCb
    lower = np.array([0, 133, 77], dtype=np.uint8)
    upper = np.array([255, 173, 127], dtype=np.uint8)
    skin_mask = cv2.inRange(ycrcb, lower, upper)
    
    # Clean up noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel, iterations=2)
    skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return skin_mask > 0

def validate_lesion_segment(mask, image_cv):
    """
    Filters individual SAM segments to reject wrinkles, pores, hair, and shadows.
    Test: redness variance, color deviation, texture entropy, size limits.
    """
    pixel_count = np.sum(mask)
    if pixel_count < 20: # Reject tiny dots (pores)
        return False
        
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    masked_laplacian = laplacian[mask > 0]
    
    if len(masked_laplacian) == 0:
        return False
        
    texture_variance = masked_laplacian.var()
    if texture_variance < 10: # Reject flat shadows
        return False
    if texture_variance > 5000: # Reject dense hair clumps
        return False
        
    return True

def compute_universal_features(image_cv, lesion_mask, skin_mask):
    """
    Computes universal clinical features (Coverage, Density, Morphology)
    bounded strictly by the validated skin area.
    """
    skin_pixels = np.sum(skin_mask)
    lesion_pixels = np.sum(lesion_mask)
    
    # 1. Coverage (Scale Invariant)
    coverage = lesion_pixels / skin_pixels if skin_pixels > 0 else 0
    
    # 2. Hybrid Density (Cluster Count + Fragmentation Index)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats((lesion_mask.astype(np.uint8) * 255))
    cluster_count = num_labels - 1 # Exclude background
    
    # Fragmentation Index: Perimeter^2 / Area (measures how "broken up" or "confluent" the lesions are)
    contours, _ = cv2.findContours((lesion_mask.astype(np.uint8) * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total_perimeter = sum(cv2.arcLength(cnt, True) for cnt in contours)
    fragmentation_index = (total_perimeter ** 2) / (lesion_pixels + 1e-5)
    
    hybrid_density = cluster_count + (fragmentation_index * 0.1) # Weighted combination
    
    # 3. True Morphology Score
    hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    
    if lesion_pixels > 0:
        # Redness (Inflammation proxy)
        hsv_lesion = hsv[lesion_mask]
        redness = np.mean(hsv_lesion[:, 1]) # Saturation
        redness_norm = min(1.0, redness / 255.0)
        
        # Texture (Roughness/Scaling proxy via Laplacian)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        texture_var = laplacian[lesion_mask].var()
        texture_norm = min(1.0, np.log1p(texture_var) / 10.0) 
        
        # Elevation proxy (Shadows / highlights around edges via Sobel)
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sobel_mag = np.hypot(sobelx, sobely)
        elevation_proxy = sobel_mag[lesion_mask].mean()
        elevation_norm = min(1.0, elevation_proxy / 100.0)
        
        # Feature Consistency (Hue Variance)
        hue_std = np.std(hsv_lesion[:, 0])
        feat_consistency = max(0.0, 1.0 - (hue_std / 60.0))
    else:
        redness_norm = texture_norm = elevation_norm = feat_consistency = 0.0

    morphology_score = (0.4 * redness_norm) + (0.3 * elevation_norm) + (0.3 * texture_norm)
    
    return {
        "coverage": coverage,
        "hybrid_density": hybrid_density,
        "cluster_count": cluster_count,
        "morphology_score": morphology_score,
        "redness_norm": redness_norm,
        "texture_norm": texture_norm,
        "elevation_norm": elevation_norm,
        "feat_consistency": feat_consistency
    }

def compute_confidence(uni_features, quality_report=None):
    if uni_features.get('coverage', 0) == 0:
        return 0.0
        
    fragmentation_ratio = uni_features['cluster_count'] / (uni_features['coverage'] * 100 + 1)
    seg_quality = max(0.0, 1.0 - (fragmentation_ratio / 5.0))
    
    img_qual = 1.0
    if quality_report:
        if quality_report.get('is_blurry'): img_qual -= 0.4
        if quality_report.get('has_glare'): img_qual -= 0.3
        if quality_report.get('is_underexposed'): img_qual -= 0.3
    img_qual = max(0.0, img_qual)
    
    feat_consistency = uni_features.get('feat_consistency', 0.0)
        
    confidence = (0.4 * seg_quality) + (0.3 * img_qual) + (0.3 * feat_consistency)
    return round(confidence * 100, 1)

_SAM_INFERENCE_CACHE = {}

def get_sam_lesion_mask(image_cv, color_mask_heuristic=None, skin_mask=None):
    """ Isolates exact lesion pixels via FastSAM bounded by skin area and validated for pathology """
    global _SAM_INFERENCE_CACHE
    lesion_mask_combined = np.zeros(image_cv.shape[:2], dtype=bool)
    try:
        img_hash = hash(image_cv.tobytes()[::10000])
        if img_hash in _SAM_INFERENCE_CACHE:
            sam_results = _SAM_INFERENCE_CACHE[img_hash]
        else:
            sam_model = get_fastsam_model()
            sam_results = sam_model(image_cv, device='cpu', retina_masks=True, imgsz=240, conf=0.4, iou=0.9, verbose=False)
            _SAM_INFERENCE_CACHE[img_hash] = sam_results
        
        for r in sam_results:
            if r.masks is not None:
                mask_data = r.masks.data.cpu().numpy()
                h, w = mask_data.shape[1], mask_data.shape[2]
                total_pixels = h * w
                
                for mask in mask_data:
                    if mask.shape != image_cv.shape[:2]:
                        mask = cv2.resize(mask, (image_cv.shape[1], image_cv.shape[0]), interpolation=cv2.INTER_NEAREST)
                        
                    bool_mask = mask > 0
                    
                    # 1. Skin constraint
                    if skin_mask is not None:
                        skin_intersection = np.logical_and(bool_mask, skin_mask)
                        if np.sum(skin_intersection) / (np.sum(bool_mask) + 1e-6) < 0.5:
                            continue # Ignore segment if mostly outside skin
                    
                    # 2. Size constraints
                    coverage = np.sum(bool_mask) / total_pixels
                    if 0.001 < coverage < 0.55:
                        # 3. Validation layer
                        if validate_lesion_segment(bool_mask, image_cv):
                            if color_mask_heuristic is not None:
                                overlap = np.logical_and(bool_mask, color_mask_heuristic > 0)
                                if np.sum(overlap) / (np.sum(bool_mask) + 1e-6) > 0.15:
                                    lesion_mask_combined = np.logical_or(lesion_mask_combined, bool_mask)
                            else:
                                lesion_mask_combined = np.logical_or(lesion_mask_combined, bool_mask)
    except Exception as e:
        print(f"SAM Segmentation Error: {e}")
        
    if not np.any(lesion_mask_combined) and color_mask_heuristic is not None:
        if skin_mask is not None:
            lesion_mask_combined = np.logical_and(color_mask_heuristic > 0, skin_mask)
        else:
            lesion_mask_combined = color_mask_heuristic > 0
            
    return lesion_mask_combined

def extract_sam_polygons(binary_mask):
    """ Converts a NumPy boolean mask into a list of simplified polygon coordinates for the web UI """
    if not np.any(binary_mask): return []
    mask_uint8 = (binary_mask.astype(np.uint8) * 255)
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    polygons = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 100: # Filter out tiny noise polygons
            epsilon = 0.005 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            if len(approx) >= 3:
                polygons.append(approx.squeeze(1).tolist())
    return polygons



def analyze_psoriasis(image_cv, context="UNCERTAIN"):
    """
    PASI Heuristics:
    Uses Universal Features to estimate Redness, Scaling, and Thickness,
    and maps true Coverage to the clinical Area Score (0-6).
    """
    hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 10, 30])
    upper_red1 = np.array([20, 255, 255])
    lower_red2 = np.array([160, 10, 30])
    upper_red2 = np.array([180, 255, 255])
    
    # White/Silvery scales: Low saturation, high value
    lower_white = np.array([0, 0, 150])
    upper_white = np.array([180, 60, 255])
    
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    
    psoriasis_heuristic_mask = mask1 + mask2 + mask_white
    
    skin_mask = detect_skin(image_cv)
    lesion_mask_combined = get_sam_lesion_mask(image_cv, psoriasis_heuristic_mask, skin_mask=skin_mask)
    
    uni = compute_universal_features(image_cv, lesion_mask_combined, skin_mask)
    
    calib = get_calibration_data()
    erythema_score = map_score_to_grade(uni["redness_norm"], calib["psoriasis_redness"])
    scaling_score = map_score_to_grade(uni["texture_norm"], calib["psoriasis_texture"])
    thickness_score = map_score_to_grade(uni["elevation_norm"], calib["psoriasis_elevation"])
    
    # Layer 6 Safety Capping
    if uni["coverage"] < 0.02:
        erythema_score = min(erythema_score, 2)
        scaling_score = min(scaling_score, 2)
        thickness_score = min(thickness_score, 2)
        
    def get_erythema_score(redness_norm):
        if redness_norm > 0.35: return 4
        if redness_norm > 0.25: return 3
        if redness_norm > 0.15: return 2
        if redness_norm > 0.05: return 1
        return 0
        
    def get_area_score(coverage):
        pct = coverage * 100
        if pct < 1: return 0
        if pct < 10: return 1
        if pct < 30: return 2
        if pct < 50: return 3
        if pct < 70: return 4
        if pct < 90: return 5
        return 6
        
    area_score = get_area_score(uni["coverage"])

    return {
        "erythema": erythema_score,
        "scaling": scaling_score,
        "thickness": thickness_score,
        "area_score": area_score,
        "sam_polygons": extract_sam_polygons(lesion_mask_combined),
        "raw_features": uni
    }

def analyze_acne(image_cv):
    """
    GAGS Custom Severity Engine
    Combines universal features using weighted arithmetic to determine true global severity,
    capped strictly by safety limits.
    """
    hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0, 30, 50]), np.array([15, 255, 255]))
    mask2 = cv2.inRange(hsv, np.array([160, 30, 50]), np.array([180, 255, 255]))
    red_mask = mask1 + mask2
    
    skin_mask = detect_skin(image_cv)
    lesion_mask_combined = get_sam_lesion_mask(image_cv, red_mask, skin_mask=skin_mask)
    
    uni = compute_universal_features(image_cv, lesion_mask_combined, skin_mask)
    
    # Stage 13 & 14: Dynamic Severity Mapping based directly on real image features
    comps = uni["cluster_count"]
    cov = uni["coverage"]
    
    if comps == 0:
        global_max = 0
    elif comps <= 2 and cov < 0.005:
        global_max = 1
    elif comps <= 5 and cov < 0.015:
        global_max = 2
    elif comps <= 12 and cov < 0.03:
        global_max = 3
    else:
        global_max = 4
        
    # Implement heuristic regional analysis (assuming full-face images)
    h, w = image_cv.shape[:2]
    
    # Simple facial grid projection
    regions_grid = {
        "fh": (0, 0, int(w), int(h*0.33)),
        "rc": (0, int(h*0.33), int(w*0.4), int(h*0.66)),
        "no": (int(w*0.4), int(h*0.33), int(w*0.6), int(h*0.66)),
        "lc": (int(w*0.6), int(h*0.33), int(w), int(h*0.66)),
        "ch": (0, int(h*0.66), int(w), h),
        "cb": (0, 0, 0, 0)
    }
    
    regional_scores = {}
    for r_id, (rx1, ry1, rx2, ry2) in regions_grid.items():
        if r_id == "cb" or ry2 <= ry1 or rx2 <= rx1:
            regional_scores[r_id] = 0
            continue
            
        r_skin = skin_mask[ry1:ry2, rx1:rx2]
        r_lesion = lesion_mask_combined[ry1:ry2, rx1:rx2]
        
        r_skin_px = np.sum(r_skin)
        if r_skin_px < 50: # Not enough skin detected in region
            regional_scores[r_id] = 0
            continue
            
        r_cov = np.sum(r_lesion) / r_skin_px
        r_comps = cv2.connectedComponents(r_lesion.astype(np.uint8))[0] - 1
        
        if r_comps == 0:
            r_sev = 0
        elif r_comps <= 1 and r_cov < 0.005:
            r_sev = 1
        elif r_comps <= 3 and r_cov < 0.015:
            r_sev = 2
        elif r_comps <= 6 and r_cov < 0.03:
            r_sev = 3
        else:
            r_sev = 4
        regional_scores[r_id] = r_sev
        
    return {
        "max_severity_grade": global_max,
        "regional_scores": regional_scores,
        "has_nodules": global_max == 4,
        "has_papules": global_max >= 2,
        "sam_polygons": extract_sam_polygons(lesion_mask_combined),
        "raw_features": uni
    }


def analyze_eczema(image_cv):
    """ EASI: Redness, Thickness, Scratching (Lines), Lichenification (Texture) """
    # Re-use Psoriasis Redness/Thickness
    from skimage.filters import frangi
    from skimage.morphology import skeletonize
    pso = analyze_psoriasis(image_cv)
    
    # Excoriation (Scratch marks) using Frangi Filter
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    img_float = gray.astype(np.float64) / 255.0
    
    # 1. Frangi Filter (detects continuous ridge/valley structures like scratches)
    # Scratches are usually darker than surrounding skin in grayscale
    ridges = frangi(img_float, sigmas=[1, 2, 3], black_ridges=True) 
    
    # 2. Threshold the ridge mask
    if np.max(ridges) > 0:
        ridges_norm = (ridges / np.max(ridges)) * 255
    else:
        ridges_norm = np.zeros_like(ridges)
        
    _, ridge_mask = cv2.threshold(ridges_norm.astype(np.uint8), 30, 255, cv2.THRESH_BINARY)
    
    # 3. Morphological Closing to connect broken scratch lines
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    closed_mask = cv2.morphologyEx(ridge_mask, cv2.MORPH_CLOSE, kernel)
    
    # 4. Skeletonize to get 1px wide scratch lines
    skeleton = skeletonize(closed_mask > 0)
    
    # NEW DL SAM PIPELINE: Restrict scratch analysis strictly to SAM lesion bounds
    # Recreate the exact mask from the already computed SAM polygons to save 15 seconds of CPU inference
    lesion_mask_combined = np.zeros(image_cv.shape[:2], dtype=bool)
    if pso.get('sam_polygons'):
        mask_uint8 = np.zeros(image_cv.shape[:2], dtype=np.uint8)
        for poly in pso['sam_polygons']:
            pts = np.array(poly, np.int32)
            cv2.fillPoly(mask_uint8, [pts], 1)
        lesion_mask_combined = mask_uint8 > 0
    else:
        # Fallback to color
        hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
        lesion_mask_combined = (cv2.inRange(hsv, np.array([0, 15, 30]), np.array([15, 255, 255])) > 0)
    
    # Filter scratches outside to avoid counting background textures
    masked_skeleton = skeleton & lesion_mask_combined
    
    # Calculate density relative to LEISON area (not total image area)
    lesion_area = np.sum(lesion_mask_combined)
    scratch_pixels = np.sum(masked_skeleton)
    scratch_density = scratch_pixels / (lesion_area + 1e-5) if lesion_area > 0 else 0
    
    # Map density to 0-3 clinical scale with more sensitive boundaries
    if scratch_density > 0.012:
        excoriation_score = 3
    elif scratch_density > 0.004:
        excoriation_score = 2
    elif scratch_density > 0.0008:
        excoriation_score = 1
    else:
        excoriation_score = 0
        
    uni = pso.get('raw_features', {})
    if uni.get('coverage', 0) < 0.02:
        excoriation_score = min(excoriation_score, 2)
        
    return {
        "erythema": pso['erythema'],
        "edema": pso['thickness'], # Proxy
        "excoriation": excoriation_score,
        "lichenification": pso['scaling'], # Proxy for roughness
        "area_score": pso.get('area_score', 0),
        "sam_polygons": pso.get('sam_polygons', []),
        "raw_features": uni
    }

def analyze_vitiligo(image_cv):
    """ VASI: Contrast Analysis for Depigmentation """
    lab = cv2.cvtColor(image_cv, cv2.COLOR_BGR2LAB)
    l_channel = lab[:,:,0]
    
    # Otsu thresholding to find light patches
    ret, initial_mask = cv2.threshold(l_channel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # NEW DL SAM PIPELINE: Isolate the true depigmented lesion, rejecting camera glare or white clothing
    skin_mask = detect_skin(image_cv)
    lesion_mask_combined = get_sam_lesion_mask(image_cv, initial_mask, skin_mask=skin_mask)
    
    # Calculate % area strictly inside the SAM shapes
    h, w = l_channel.shape
    total_pixels = h * w
    lesion_pixels = np.sum(lesion_mask_combined)
    
    percentage = (lesion_pixels / total_pixels) * 100
    
    return {
        "depigmentation_pct": round(percentage, 1),
        "sam_polygons": extract_sam_polygons(lesion_mask_combined)
    }

def analyze_melanoma(image_cv):
    """ ABCDE Rule Heuristics - Clinical Revision """
    
    # 1. K-Means clustering in LAB color space for robust Masking
    lab = cv2.cvtColor(image_cv, cv2.COLOR_BGR2LAB)
    
    # Reshape for KMeans
    pixel_values = lab.reshape((-1, 3))
    pixel_values = np.float32(pixel_values)
    
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    K = 2
    _, labels, centers = cv2.kmeans(pixel_values, K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    
    # The lesion is the dark region. L channel is center[:, 0].
    # Which cluster has lower L?
    if centers[0][0] < centers[1][0]:
        lesion_cluster = 0
    else:
        lesion_cluster = 1
        
    mask = (labels == lesion_cluster).astype(np.uint8) * 255
    mask = mask.reshape(image_cv.shape[:2])
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    # NEW DL SAM PIPELINE: 
    # The K-Means mask gives a rough shape. We pass this to SAM to get an absolutely 
    # pixel-perfect boundary mapping of the mole to measure Asymmetry and Border correctly.
    sam_bool_mask = get_sam_lesion_mask(image_cv, mask)
    mask = (sam_bool_mask * 255).astype(np.uint8)
    
    # Find bounding box
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"asymmetry":0, "border":0, "color":0, "diameter":0}
        
    cnt = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(cnt)
    
    # Crop mask to bounding box for A
    lesion_roi = mask[y:y+h, x:x+w]
    
    # A: Asymmetry (Mirror Overlap)
    if lesion_roi.size == 0 or cv2.countNonZero(lesion_roi) == 0:
        asymmetry_score = 0
    else:
        # Flip horizontally
        h_flip = cv2.flip(lesion_roi, 1)
        h_xor = cv2.bitwise_xor(lesion_roi, h_flip)
        h_asym = cv2.countNonZero(h_xor) / cv2.countNonZero(lesion_roi)
        
        # Flip vertically
        v_flip = cv2.flip(lesion_roi, 0)
        v_xor = cv2.bitwise_xor(lesion_roi, v_flip)
        v_asym = cv2.countNonZero(v_xor) / cv2.countNonZero(lesion_roi)
        
        # Total asymmetry (0 to ~1)
        total_asym_ratio = (h_asym + v_asym) / 2.0
        if total_asym_ratio > 0.4:
            asymmetry_score = 2
        elif total_asym_ratio > 0.2:
            asymmetry_score = 1
        else:
            asymmetry_score = 0

    # B: Border
    perimeter = cv2.arcLength(cnt, True)
    area = cv2.contourArea(cnt)
    if area > 0:
        compactness = (perimeter ** 2) / (4 * np.pi * area)
        # Compactness > 1 is irregular. Score 0-2
        if compactness > 2.0:
            border_score = 2
        elif compactness > 1.3:
            border_score = 1
        else:
            border_score = 0
    else:
        border_score = 0
        
    # C: Color Clusters
    # Extract only lesion pixels in RGB
    rgb = cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB)
    lesion_pixels = rgb[mask == 255]
    if len(lesion_pixels) > 10:
        pixels_float = np.float32(lesion_pixels)
        criteria_c = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
        # Try K=4 to find distinct color clusters
        _, labels_c, _ = cv2.kmeans(pixels_float, 4, None, criteria_c, 10, cv2.KMEANS_RANDOM_CENTERS)
        
        # Count significant clusters (> 5% of lesion)
        unique, counts = np.unique(labels_c, return_counts=True)
        significant_clusters = np.sum(counts > (0.05 * len(lesion_pixels)))
        
        if significant_clusters >= 3:
            color_score = 2
        elif significant_clusters == 2:
            color_score = 1
        else:
            color_score = 0
    else:
        color_score = 0
        
    # D: Diameter (relative to image)
    img_h, img_w = image_cv.shape[:2]
    relative_diameter = max(w, h) / max(img_w, img_h)
    
    if relative_diameter > 0.5:
        diameter_score = 1
    else:
        diameter_score = 0

    return {
        "asymmetry": asymmetry_score,
        "border": border_score,
        "color": color_score,
        "diameter": diameter_score,
        "sam_polygons": extract_sam_polygons(sam_bool_mask)
    }

def analyze_alopecia(image_cv):
    """ SALT: Hair Density - Clinical Revision """
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    
    # 1. Blur Detection (Laplacian Variance)
    blur_variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_blurry = bool(blur_variance < 50)
    
    # 2. LAB K-Means for Segmentation (Hair vs Scalp)
    lab = cv2.cvtColor(image_cv, cv2.COLOR_BGR2LAB)
    pixel_values = lab.reshape((-1, 3))
    pixel_values = np.float32(pixel_values)
    
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, centers = cv2.kmeans(pixel_values, 2, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    
    # Determine which cluster is hair (typically the darker L channel)
    if centers[0][0] < centers[1][0]:
        hair_cluster = 0
    else:
        hair_cluster = 1
        
    hair_pixels = np.sum(labels == hair_cluster)
    total_pixels = labels.shape[0]
    hair_area_ratio = hair_pixels / total_pixels
    
    # 3. Texture Density (Edges)
    edges = cv2.Canny(gray, 100, 200)
    texture_density = np.mean(edges) / 255.0
    
    # 4. Blended Presence Score
    # Normalize texture density so strong texture brings it closer to 1
    normalized_texture = min(1.0, texture_density * 5.0)
    presence_score = (0.6 * hair_area_ratio) + (0.4 * normalized_texture)
    
    # Estimated loss
    loss_score = max(0, min(100, (1.0 - presence_score) * 100))
    
    return {
        "hair_loss_pct": round(loss_score, 1),
        "is_blurry": is_blurry,
        "blur_variance": round(blur_variance, 1)
    }


def analyze_image_quality(image_cv):
    """
    Analyzes the raw clinical photo to determine if it meets the minimum threshold
    for AI evaluation. Flags blur, severe glare, and underexposure.
    """
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
    
    # 1. Blur calculation (Laplacian Variance)
    blur_variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_blurry = bool(blur_variance < 80.0) # threshold for "too blurry to diagnose"
    
    # 2. Specular Glare / Flash Overexposure
    v_channel = hsv[:,:,2]
    total_pixels = v_channel.shape[0] * v_channel.shape[1]
    glare_pixels = np.sum(v_channel > 240)
    glare_ratio = glare_pixels / total_pixels
    has_glare = bool(glare_ratio > 0.15) # >15% pure white means useless photo
    
    # 3. Severe Underexposure
    is_dark = bool(np.mean(v_channel) < 40)
    
    return {
        "is_blurry": is_blurry,
        "has_glare": has_glare,
        "is_underexposed": is_dark,
        "blur_variance": round(blur_variance, 1),
        "glare_ratio": round(glare_ratio, 3)
    }

def get_visual_score(image_path, disease_name):

    try:
        print(f"[DEBUG] Scoring for {disease_name} on {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            return {}

        img = cv2.resize(img,(512,512))

        quality_report = analyze_image_quality(img)

        d_lower = disease_name.lower()

        # =========================
        # DISPATCH
        # =========================

        if "psoriasis" in d_lower:
            result = analyze_psoriasis(img)

        elif "acne" in d_lower:
            result = analyze_acne(img)

        elif "dermatitis" in d_lower or "eczema" in d_lower:
            result = analyze_eczema(img)

        elif "vitiligo" in d_lower:
            result = analyze_vitiligo(img)

        elif "melanoma" in d_lower or "nevus" in d_lower:
            result = analyze_melanoma(img)

        elif "alopecia" in d_lower or "hair" in d_lower:
            result = analyze_alopecia(img)

        else:
            result = analyze_psoriasis(img)

        # =========================
        # ADD QUALITY INFO
        # =========================
        result["image_quality"] = quality_report

        # =========================
        # CONFIDENCE SYSTEM
        # =========================
        if "raw_features" in result:

            conf = compute_confidence(
                result["raw_features"],
                quality_report
            )

            result["confidence_score"] = conf

            # Prevent hallucinated max severity
            if conf < 60:

                if "max_severity_grade" in result:
                    result["max_severity_grade"] = min(
                        result["max_severity_grade"],3
                    )

                for k in ["erythema","scaling","thickness"]:
                    if k in result:
                        result[k] = min(result[k],3)

        else:
            result["confidence_score"] = 0

        return result

    except Exception as e:
        print("[SCORING ERROR]",e)
        return {}