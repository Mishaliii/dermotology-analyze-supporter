import cv2
import numpy as np
from PIL import Image

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
    GAGS Heuristics:
    - Count red blobs (Papules/Nodules).
    - Count dark blobs (Comedones).
    """
    # Simple blob detector for red spots
    params = cv2.SimpleBlobDetector_Params()
    params.filterByColor = False
    params.filterByArea = True
    params.minArea = 15
    params.maxArea = 500
    params.filterByCircularity = True
    params.minCircularity = 0.3
    
    detector = cv2.SimpleBlobDetector_create(params)
    
    # Process Red Channel for inflammation
    b, g, r = cv2.split(image_cv)
    # Invert R to make red spots dark for detection? 
    # Actually standard blob detection works on dark blobs on light background usually.
    # Let's try thresholding red.
    hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255])) # Red mask
    mask2 = cv2.inRange(hsv, np.array([170, 70, 50]), np.array([180, 255, 255]))
    red_mask = mask1 + mask2
    
    # Count connected components in red mask
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(red_mask)
    
    # Filter by size
    papules = 0
    nodules = 0
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if 10 < area < 100:
            papules += 1
        elif area >= 100:
            nodules += 1
            
    return {
        "comedones": 0, # Hard to detect without zoom
        "papules": papules,
        "nodules": modules_estimate := nodules,
        "score_preview": papules + (nodules * 2) 
    }

def analyze_eczema(image_cv):
    """ EASI: Redness, Thickness, Scratching (Lines), Lichenification (Texture) """
    # Re-use Psoriasis Redness/Thickness
    pso = analyze_psoriasis(image_cv)
    
    # Scratch marks (Lines)
    edges = cv2.Canny(image_cv, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, minLineLength=30, maxLineGap=10)
    scratch_score = min(3, int(len(lines)/5)) if lines is not None else 0
    
    return {
        "erythema": pso['erythema'],
        "edema": pso['thickness'], # Proxy
        "excoriation": scratch_score,
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
    """ ABCDE Rule Heuristics """
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    ret, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # A: Asymmetry
    M = cv2.moments(mask)
    if M["m00"] == 0: return {"asymmetry":0, "border":0, "color":0, "diameter":0}
    
    cX = int(M["m10"] / M["m00"])
    cY = int(M["m01"] / M["m00"])
    
    # Bounding Box
    x,y,w,h = cv2.boundingRect(mask)
    center_box_x = x + w//2
    center_box_y = y + h//2
    
    diff = np.sqrt((cX - center_box_x)**2 + (cY - center_box_y)**2)
    asymmetry_score = min(10, int(diff / 5))
    
    # B: Border (Compactness)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cnt = max(contours, key=cv2.contourArea)
        perimeter = cv2.arcLength(cnt, True)
        area = cv2.contourArea(cnt)
        if area > 0:
            compactness = (perimeter ** 2) / (4 * np.pi * area)
            border_score = min(10, int(compactness - 1))
        else:
            border_score = 0
    else:
        border_score = 0
        
    # C: Color Var
    mean, std = cv2.meanStdDev(image_cv, mask=mask)
    color_var = np.mean(std) 
    color_score = min(10, int(color_var / 5))

    return {
        "asymmetry": asymmetry_score,
        "border": border_score,
        "color": color_score,
        "diameter": min(10, int(w/50)) # Relative pixels
    }

def analyze_alopecia(image_cv):
    """ SALT: Hair Density """
    # Texture analysis on gray
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    
    # Edge density
    edges = cv2.Canny(gray, 100, 200)
    edge_density = np.mean(edges) / 255.0
    
    # Inverse logic: Low edge density -> Smooth Scalp -> Hair Loss
    # High edge density -> Hair strands
    
    loss_score = 0
    if edge_density < 0.05: loss_score = 100 # Smooth
    elif edge_density < 0.1: loss_score = 50
    else: loss_score = 10
    
    return {
        "hair_loss_pct": loss_score,
        "scalp_coverage": 100 - loss_score
    }


def get_visual_score(image_path, disease_name):
    """
    Main entry point. Dispatches to specific function.
    """
    try:
        img = cv2.imread(image_path)
        if img is None: return {}
        
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
