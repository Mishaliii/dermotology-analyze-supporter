import numpy as np
from PIL import Image
import os
from collections import defaultdict
import psycopg
import traceback

# Lazy modules (loaded on demand)
torch = None
faiss = None

# DB Config
DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def get_db_connection():
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    return psycopg.connect(conn_str)

# =============================
# CONFIG
# =============================
MODEL_NAME = "facebook/dinov2-base"
DEVICE = "cpu"
EMBEDDING_DIR = "embeddings"

KNN_K = 15          # how many neighbors to retrieve for voting
SEARCH_K = 50       # how many to retrieve for evidence context

# =============================
# LAZY MODEL LOADING
# =============================
processor = None
model = None
image_labels = None
image_paths = None
cls_index = None
models_loaded = False

def load_models():
    global processor, model, image_labels, image_paths, cls_index, models_loaded, torch, faiss
    if models_loaded:
        return
    
    print("[INFO] Loading DINOv2 Model and FAISS indices...")
    # Import heavy libraries only when needed
    import torch as _torch
    import faiss as _faiss
    from transformers import AutoImageProcessor, AutoModel

    # Save into global variables so they can be used across functions
    torch = _torch
    faiss = _faiss

    def _load_transformers_assets(disable_ssl: bool = False):
        if disable_ssl:
            os.environ["HF_HUB_DISABLE_SSL_VERIFICATION"] = "1"
        else:
            os.environ.pop("HF_HUB_DISABLE_SSL_VERIFICATION", None)

        try:
            return (
                AutoImageProcessor.from_pretrained(MODEL_NAME, use_fast=False, local_files_only=True),
                AutoModel.from_pretrained(MODEL_NAME, local_files_only=True),
            )
        except Exception:
            return (
                AutoImageProcessor.from_pretrained(MODEL_NAME, use_fast=False),
                AutoModel.from_pretrained(MODEL_NAME),
            )

    try:
        processor, model = _load_transformers_assets(disable_ssl=False)
    except Exception as first_exc:
        print(f"[WARN] DINOv2 local/standard load failed, retrying with SSL verification disabled: {first_exc}")
        try:
            processor, model = _load_transformers_assets(disable_ssl=True)
        except Exception as second_exc:
            print("[ERROR] DINOv2 load failed on both attempts:")
            traceback.print_exc()
            raise second_exc

    model.eval().to(DEVICE)
    torch.set_grad_enabled(False)
    
    # PostgreSQL completely replaces the need to load .npy arrays into memory.
    # We only load FAISS geometry into RAM.
    
    cls_index = faiss.read_index(os.path.join(EMBEDDING_DIR, "cls_index.faiss"))
    models_loaded = True
    print("[INFO] Model and Data loaded successfully.")

# =============================
# CORE FUNCTIONS
# =============================

def embed_image(image: Image.Image):
    """
    Returns (cls_embedding, mean_embedding) with Test Time Augmentation (TTA)
    Averages embeddings from: Original, Flip, and Zoom.
    """
    # 1. Base Image (Squish Resize)
    img_base = image.resize((224, 224))
    
    # 2. Horizontal Flip
    img_flip = img_base.transpose(Image.FLIP_LEFT_RIGHT)
    
    # 3. 90% Zoom (Crop center 200x200 and resize back)
    # 224 * 0.1 = ~22px margin. 224 - 22 = 202.
    img_zoom = img_base.crop((22, 22, 202, 202)).resize((224, 224))
    
    # Process batch of 3
    load_models()
    inputs = processor(images=[img_base, img_flip, img_zoom], return_tensors="pt", do_resize=False, do_center_crop=False)
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
    
    # Extract Embeddings (Batch Size = 3)
    # CLS: [3, 768]
    cls_batch = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    
    # Average across the 3 views (TTA)
    # Using keepdims=True ensures shape is (1, 768) instead of (768,)
    # This is critical for FAISS compatibility.
    cls_emb = cls_batch.mean(axis=0, keepdims=True)
    
    return cls_emb

def knn_vote(query_embedding: np.ndarray, index, knn_k=KNN_K, search_k=SEARCH_K):
    """
    Generic KNN voting with 'Top Match Bonus'
    Searches deeper (search_k) for evidence, votes on top (knn_k).
    Resolves indices against PostgreSQL.
    """
    q = query_embedding.copy()
    faiss.normalize_L2(q)

    # Search deeper to find evidence for Method 2
    scores, indices = index.search(q, search_k)

    disease_votes = defaultdict(float)
    similar_cases = []
    champion_bonus = 0.0

    # Batch Query the DB for all retrieved faiss_ids
    # Convert np indices to Python ints to avoid psycopg parameter errors
    faiss_ids_to_query = [int(idx) for idx in indices[0]]
    id_to_metadata = {}
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Query all hits in one go for speed
            query = """
                SELECT i.faiss_id, i.relative_path, d.name 
                FROM images i
                JOIN diseases d ON i.disease_id = d.id
                WHERE i.faiss_id = ANY(%s)
            """
            cur.execute(query, (faiss_ids_to_query,))
            for row in cur.fetchall():
                faiss_id, r_path, d_name = row
                id_to_metadata[faiss_id] = {"path": r_path, "disease": d_name}

    for i, (sim, idx) in enumerate(zip(scores[0], indices[0])):
        idx = int(idx)
        if idx not in id_to_metadata:
            continue
            
        metadata = id_to_metadata[idx]
        disease = metadata["disease"]
        score = float(sim)
        
        # Collect ALL retrieved neighbors as potential evidence/context
        similar_cases.append({
            "image_path": metadata["path"],
            "disease": disease,
            "similarity": float(sim)
        })

        # VOTING LOGIC: Only count top knn_k neighbors
        if i < knn_k:
            # 'Champion Bonus': The single best match gets a huge boost
            if i == 0:
                if score > 0.90:
                    score += 10.0  # Massive bonus: 1-NN override
                    champion_bonus = 10.0
                else:
                    score += 2.0   # Moderate bonus: priority
                    champion_bonus = 2.0
                
            disease_votes[disease] += score

    # Rank diseases by weighted vote
    ranked_diseases = sorted(
        disease_votes.items(),
        key=lambda x: -x[1]
    )

    return ranked_diseases, similar_cases, champion_bonus




def get_dynamic_top_diseases(ranked_diseases, max_diseases=5, threshold_ratio=0.4, min_diseases=2, champion_bonus=0.0):
    """
    Returns diseases that score within `threshold_ratio` of the top prediction,
    while guaranteeing at least `min_diseases` are returned if available.
    Ensures we don't drop viable differential diagnoses, but filters out junk.
    """
    if not ranked_diseases:
        return []
        
    result = []
    top_score = ranked_diseases[0][1]
    
    # Strip the artificial Champion Bonus from the top score just for this threshold check
    # to prevent perfectly valid 2nd/3rd place diseases from getting wiped out by a massive +10 vote
    pure_top_score = max(0.01, top_score - champion_bonus)
    threshold = pure_top_score * threshold_ratio
    
    for i, (disease, score) in enumerate(ranked_diseases):
        # Always include the minimum guaranteed number of diseases
        if i < min_diseases:
            result.append((disease, score))
        # For remaining diseases, check if they meet the threshold
        elif score >= threshold and len(result) < max_diseases:
            result.append((disease, score))
            
    return result


def build_analysis_decision(similar_cases):
    """
    Build a conservative triage decision for non-disease detection.
    This is additive metadata only and does not alter disease suggestions.
    """
    if not similar_cases:
        return {
            "candidate_status": "no_disease_candidate",
            "decision_confidence": 0.95,
            "reject_reasons": ["no_similar_cases"],
            "signals": {
                "top1_similarity": 0.0,
                "top2_similarity": 0.0,
                "avg_top3_similarity": 0.0,
                "top1_top2_gap": 0.0,
            },
        }

    disease_max_sim = {}
    for case in similar_cases:
        disease = str(case.get("disease") or "Unknown")
        sim = float(case.get("similarity") or 0.0)
        prev = disease_max_sim.get(disease, 0.0)
        if sim > prev:
            disease_max_sim[disease] = sim

    ranked = sorted(disease_max_sim.items(), key=lambda x: -x[1])
    top_scores = [float(score) for _, score in ranked[:3]]

    top1 = top_scores[0] if len(top_scores) > 0 else 0.0
    top2 = top_scores[1] if len(top_scores) > 1 else 0.0
    avg_top3 = float(sum(top_scores) / len(top_scores)) if top_scores else 0.0
    gap = top1 - top2

    # Conservative defaults; tune later with shadow logs.
    t_top1 = 0.58
    t_avg3 = 0.52
    t_gap = 0.06

    c_top1 = top1 < t_top1
    c_avg3 = avg_top3 < t_avg3
    c_gap = gap < t_gap

    reasons = []
    if c_top1:
        reasons.append("low_top1_similarity")
    if c_avg3:
        reasons.append("low_avg_top3_similarity")
    if c_gap:
        reasons.append("small_top1_top2_gap")

    true_count = sum([1 if c_top1 else 0, 1 if c_avg3 else 0, 1 if c_gap else 0])

    if true_count == 3:
        status = "no_disease_candidate"
        confidence = 0.85
    elif true_count >= 2:
        status = "uncertain"
        confidence = 0.6
    else:
        status = "likely_disease"
        confidence = 0.8

    return {
        "candidate_status": status,
        "decision_confidence": confidence,
        "reject_reasons": reasons,
        "signals": {
            "top1_similarity": round(top1, 4),
            "top2_similarity": round(top2, 4),
            "avg_top3_similarity": round(avg_top3, 4),
            "top1_top2_gap": round(gap, 4),
        },
        "thresholds": {
            "top1_similarity_lt": t_top1,
            "avg_top3_similarity_lt": t_avg3,
            "top1_top2_gap_lt": t_gap,
        },
    }


def analyze_skin_image(image_path: str, knn_k=KNN_K, search_k=SEARCH_K):
    load_models()
    image = Image.open(image_path).convert("RGB")
    cls_emb = embed_image(image)

    # ---------------------------------------------------------
    # Final AI Match: CLS + Rank-Weighted kNN
    # ---------------------------------------------------------
    m1_ranks, m1_cases, m1_bonus = knn_vote(cls_emb, cls_index, knn_k=knn_k, search_k=search_k)
            
    # --- DYNAMIC DISEASE SELECTION ---
    dynamic_m1_ranks = get_dynamic_top_diseases(m1_ranks, champion_bonus=m1_bonus)

    # --- SEVERITY SCORING ---
    # Scoring is deferred entirely to on-demand via /score_disease endpoint.
    # This makes the initial /analyze response near-instant (no FastSAM on CPU).
    # The frontend will call /score_disease when the user clicks a disease chip.
    severity_assessments = []
    analysis_decision = build_analysis_decision(m1_cases[:30])

    return {
        "cls_knn": {
            "top_diseases": dynamic_m1_ranks,
            "similar_cases": m1_cases[:30]
        },
        "analysis_decision": analysis_decision,
        "severity_assessments": severity_assessments,
        # Pass back the uploaded image path so the on-demand scorer can use it
        "analyzed_image_path": image_path
    }
