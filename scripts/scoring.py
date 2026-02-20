import cv2
import numpy as np
from skimage.filters import frangi
from skimage.morphology import skeletonize

def analyze_psoriasis(image_cv):
    """
    PASI Heuristics:
    - Erythema (Redness): Mean saturation of red pixels.
    - Induration (Thickness): (Proxy) Texture contrast.
    - Desquamation (Scaling): High-frequency edge detection.
    """
    # 1. Erythema (Redness)
    hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
    # Target Red ranges
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 50, 50])
    upper_red2 = np.array([180, 255, 255])
    
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = mask1 + mask2
    
    red_saturation = np.mean(hsv[:,:,1][red_mask > 0]) if np.count_nonzero(red_mask) > 0 else 0
    # Map 0-255 to 0-4
    erythema_score = min(4, int(red_saturation / 50)) 

    # 2. Desquamation (Scaling - White/Silvery)
    # Detect high frequencies (edges) in Value channel
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    variance = laplacian.var()
    # Logarithmic mapping for variance to 0-4
    scaling_score = min(4, int(np.log1p(variance) / 2))

    # 3. Induration (Thickness) - Hard to do in 2D, estimate from contrast
    contrast = image_cv.std()
    thickness_score = min(4, int(contrast / 15))

    return {
        "erythema": erythema_score,
        "scaling": scaling_score,
        "thickness": thickness_score,
        "area_score": 0 # Doctor input
    }

def analyze_acne(image_cv):
    """
    GAGS Heuristics - Clinical Revision:
    - GAGS does not sum lesions. It assigns a single Severity Grade per region
      based on the most severe lesion present.
    - Grades: 0=Clear, 1=Comedones, 2=Papules, 3=Pustules, 4=Nodules
    """
    # Process Red Channel for inflammation
    hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
    mask2 = cv2.inRange(hsv, np.array([170, 70, 50]), np.array([180, 255, 255]))
    red_mask = mask1 + mask2
    
    # Count connected components in red mask
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(red_mask)
    
    # Analyze all blobs to find max severity
    has_nodule = False
    has_papule = False
    
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= 100:
            has_nodule = True
        elif 10 < area < 100:
            has_papule = True
            
    # Determine maximum grade present
    max_grade = 0
    if has_nodule:
        max_grade = 4
    elif has_papule:
        max_grade = 2
    else:
        # Assuming 0 if no clear red inflammation (ignoring comedones for basic CV)
        max_grade = 0
        
    return {
        "max_severity_grade": max_grade,
        "has_nodules": has_nodule,
        "has_papules": has_papule
    }

def analyze_eczema(image_cv):
    """ EASI: Redness, Thickness, Scratching (Lines), Lichenification (Texture) """
    # Re-use Psoriasis Redness/Thickness
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
    
    # Calculate density relative to image area
    h, w = gray.shape
    total_area = h * w
    scratch_pixels = np.sum(skeleton)
    scratch_density = scratch_pixels / (total_area + 1e-5)
    
    # Map density (0.0 to ~0.02) to 0-3 clinical scale
    if scratch_density > 0.015:
        excoriation_score = 3
    elif scratch_density > 0.005:
        excoriation_score = 2
    elif scratch_density > 0.001:
        excoriation_score = 1
    else:
        excoriation_score = 0
    
    return {
        "erythema": pso['erythema'],
        "edema": pso['thickness'], # Proxy
        "excoriation": excoriation_score,
        "lichenification": pso['scaling'] # Proxy for roughness
    }

def analyze_vitiligo(image_cv):
    """ VASI: Contrast Analysis for Depigmentation """
    # Convert to LAB
    lab = cv2.cvtColor(image_cv, cv2.COLOR_BGR2LAB)
    l_channel = lab[:,:,0]
    
    # Otsu thresholding to find light patches
    # In Vitiligo, lesions are very bright (High L)
    ret, mask = cv2.threshold(l_channel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Calculate % area
    h, w = l_channel.shape
    total_pixels = h * w
    lesion_pixels = cv2.countNonZero(mask)
    
    # Heuristic: If >50% is light, maybe checks skin tone. 
    # Valid assumption: Lesion is lighter than background skin.
    percentage = (lesion_pixels / total_pixels) * 100
    
    return {
        "depigmentation_pct": round(percentage, 1),
        "hand_units": round(percentage, 1) # 1 Hand Unit ~= 1%
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
    
    # Clean up mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
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
        "diameter": diameter_score
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


def get_visual_score(image_path, disease_name):
    """
    Main entry point. Dispatches to specific function.
    """
    try:
        print(f"[DEBUG] Scoring for {disease_name} on {image_path}")
        img = cv2.imread(image_path)
        if img is None: 
            print("[DEBUG] Failed to load image")
            return {}
        
        # Resize for consistent processing
        img = cv2.resize(img, (512, 512))

        d_lower = disease_name.lower()
        
        if "psoriasis" in d_lower:
            return analyze_psoriasis(img)
        elif "acne" in d_lower:
            return analyze_acne(img)
        elif "dermatitis" in d_lower or "eczema" in d_lower:
            return analyze_eczema(img)
        elif "vitiligo" in d_lower:
            return analyze_vitiligo(img)
        elif "melanoma" in d_lower or "nevus" in d_lower:
            return analyze_melanoma(img)
        elif "alopecia" in d_lower or "hair" in d_lower:
            return analyze_alopecia(img)
        else:
            # Default fallback (generic intensity)
            return analyze_psoriasis(img) # Returns generic R/G/B metrics
            
    except Exception as e:
        print(f"[SCORING ERROR] {e}")
        return {}
