import torch
import numpy as np
import faiss
from PIL import Image
from transformers import AutoImageProcessor, AutoModel
import os
from collections import defaultdict

# =============================
# CONFIG
# =============================
MODEL_NAME = "facebook/dinov2-base"
DEVICE = "cpu"
EMBEDDING_DIR = "embeddings"

KNN_K = 15          # how many neighbors to retrieve for voting
SEARCH_K = 50       # how many to retrieve for evidence context
TOP_DISEASES = 2    # max diseases to report

# =============================
# LOAD MODEL
# =============================
processor = AutoImageProcessor.from_pretrained(MODEL_NAME, use_fast=False)
model = AutoModel.from_pretrained(MODEL_NAME)
model.eval().to(DEVICE)
torch.set_grad_enabled(False)

# =============================
# LOAD DATA
# =============================
image_labels = np.load(
    os.path.join(EMBEDDING_DIR, "image_labels.npy"),
    allow_pickle=True
)
image_paths = np.load(
    os.path.join(EMBEDDING_DIR, "image_paths.npy"),
    allow_pickle=True
)

cls_index = faiss.read_index(os.path.join(EMBEDDING_DIR, "cls_index.faiss"))
mean_index = faiss.read_index(os.path.join(EMBEDDING_DIR, "mean_index.faiss"))

disease_centroids = np.load(
    os.path.join(EMBEDDING_DIR, "disease_mean_vectors.npy"),
    allow_pickle=True
).item()

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
    inputs = processor(images=[img_base, img_flip, img_zoom], return_tensors="pt", do_resize=False, do_center_crop=False)
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
    
    # Extract Embeddings (Batch Size = 3)
    # CLS: [3, 768]
    cls_batch = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    # Mean: [3, 768]
    mean_batch = outputs.last_hidden_state.mean(dim=1).cpu().numpy()
    
    # Average across the 3 views (TTA)
    # Using keepdims=True ensures shape is (1, 768) instead of (768,)
    # This is critical for FAISS compatibility.
    cls_emb = cls_batch.mean(axis=0, keepdims=True)
    mean_emb = mean_batch.mean(axis=0, keepdims=True)
    
    return cls_emb, mean_emb

def knn_vote(query_embedding: np.ndarray, index, knn_k=KNN_K, search_k=SEARCH_K):
    """
    Generic KNN voting with 'Top Match Bonus'
    Searches deeper (search_k) for evidence, votes on top (knn_k).
    """
    q = query_embedding.copy()
    faiss.normalize_L2(q)

    # Search deeper to find evidence for Method 2
    scores, indices = index.search(q, search_k)

    disease_votes = defaultdict(float)
    similar_cases = []

    for i, (sim, idx) in enumerate(zip(scores[0], indices[0])):
        disease = image_labels[idx]
        score = float(sim)
        
        # Collect ALL retrieved neighbors as potential evidence/context
        similar_cases.append({
            "image_path": image_paths[idx],
            "disease": disease,
            "similarity": float(sim)
        })

        # VOTING LOGIC: Only count top knn_k neighbors
        if i < knn_k:
            # 'Champion Bonus': The single best match gets a huge boost
            if i == 0:
                if score > 0.90:
                    score += 10.0  # Massive bonus: 1-NN override
                else:
                    score += 2.0   # Moderate bonus: priority
                
            disease_votes[disease] += score

    # Rank diseases by weighted vote
    ranked_diseases = sorted(
        disease_votes.items(),
        key=lambda x: -x[1]
    )

    return ranked_diseases, similar_cases


def cosine_centroid_search(query_embedding: np.ndarray):
    """
    Compare query against disease centroids
    """
    q = query_embedding.flatten()
    q = q / np.linalg.norm(q)  # Normalize query
    
    scores = {}
    for disease, centroid in disease_centroids.items():
        centroid = centroid / np.linalg.norm(centroid) # Normalize centroid
        sim = np.dot(q, centroid)
        scores[disease] = float(sim)
        
    ranked_diseases = sorted(scores.items(), key=lambda x: -x[1])
    return ranked_diseases[:TOP_DISEASES]


def analyze_skin_image(image_path: str, knn_k=KNN_K, search_k=SEARCH_K):
    image = Image.open(image_path).convert("RGB")
    cls_emb, mean_emb = embed_image(image)

    # ---------------------------------------------------------
    # Method 1: CLS + Rank-Weighted kNN
    # ---------------------------------------------------------
    m1_ranks, m1_cases = knn_vote(cls_emb, cls_index, knn_k=knn_k, search_k=search_k)
    
    # ---------------------------------------------------------
    # Method 2: Mean + Cosine Similarity (Centroids)
    # ---------------------------------------------------------
    # 1. Predict Disease using Centroids
    m2_ranks = cosine_centroid_search(mean_emb)
    
    # 2. Find Evidence (Similar Cases for the predicted disease)
    # We perform a search specifically for this method's evidence, 
    # filtering for the top predicted disease.
    m2_top_disease = m2_ranks[0][0]
    
    # Normalized query for search
    q_mean = mean_emb.copy()
    faiss.normalize_L2(q_mean)
    D, I = mean_index.search(q_mean, search_k)
    
    m2_cases = []
    # Look through the search results to find instances of the top predicted disease
    for dist, idx in zip(D[0], I[0]):
        disease = image_labels[idx]
        if disease == m2_top_disease:
            m2_cases.append({
                "image_path": image_paths[idx],
                "disease": disease,
                "similarity": float(dist)
            })
            if len(m2_cases) >= 5: # Limit to top 5 evidence
                break

    # ---------------------------------------------------------
    # Method 3: Mean + Rank-Weighted kNN (Texture)
    # ---------------------------------------------------------
    m3_ranks, m3_cases = knn_vote(mean_emb, mean_index, knn_k=knn_k, search_k=search_k)
            
    # --- SEVERITY SCORING ---
    # Calculate score for ALL top diseases from Method 1
    severity_assessments = []
    
    try:
        from scripts.scoring import get_visual_score
        
        for disease, _ in m1_ranks[:TOP_DISEASES]:
            metrics = get_visual_score(image_path, disease)
            severity_assessments.append({
                "disease": disease,
                "metrics": metrics
            })
            
    except ImportError as e:
        print(f"WARNING: scoring import failed: {e}")
    except Exception as e:
        print(f"SCORING ERROR: {e}")

    return {
        "cls_knn": {
            "top_diseases": m1_ranks[:TOP_DISEASES],
            "similar_cases": m1_cases[:5]
        },
        "mean_cosine": {
            "top_diseases": m2_ranks,
            "similar_cases": m2_cases
        },
        "mean_knn": {
            "top_diseases": m3_ranks[:TOP_DISEASES],
            "similar_cases": m3_cases[:5]
        },
        "severity_assessments": severity_assessments 
    }

    return {
        "cls_knn": {
            "top_diseases": m1_ranks[:TOP_DISEASES],
            "similar_cases": m1_cases[:5]
        },
        "mean_cosine": {
            "top_diseases": m2_ranks,
            "similar_cases": m2_cases
        },
        "mean_knn": {
            "top_diseases": m3_ranks[:TOP_DISEASES],
            "similar_cases": m3_cases[:5]
        },
        "severity_assessment": {
            "disease": primary_diagnosis,
            "metrics": severity_data
        }
    }
