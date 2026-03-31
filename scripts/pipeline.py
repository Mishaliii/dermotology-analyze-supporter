import numpy as np
from PIL import Image
import os
from collections import defaultdict
import psycopg

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

    processor = AutoImageProcessor.from_pretrained(MODEL_NAME, use_fast=False)
    model = AutoModel.from_pretrained(MODEL_NAME)
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

    return {
        "cls_knn": {
            "top_diseases": dynamic_m1_ranks,
            "similar_cases": m1_cases[:30]
        },
        "severity_assessments": severity_assessments,
        # Pass back the uploaded image path so the on-demand scorer can use it
        "analyzed_image_path": image_path
    }
