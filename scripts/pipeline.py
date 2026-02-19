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

KNN_K = 15          # how many neighbors to retrieve
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
    """Returns (cls_embedding, mean_embedding)"""
    # Resize (squish) to 224x224 and disable processor's default cropping
    image = image.resize((224, 224))
    inputs = processor(images=image, return_tensors="pt", do_resize=False, do_center_crop=False)
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    
    cls_emb = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    mean_emb = outputs.last_hidden_state.mean(dim=1).cpu().numpy()
    return cls_emb, mean_emb


def knn_vote(query_embedding: np.ndarray, index):
    """
    Generic KNN voting with 'Top Match Bonus'
    """
    q = query_embedding.copy()
    faiss.normalize_L2(q)

    scores, indices = index.search(q, KNN_K)

    disease_votes = defaultdict(float)
    similar_cases = []

    for i, (sim, idx) in enumerate(zip(scores[0], indices[0])):
        disease = image_labels[idx]
        score = float(sim)
        
        # 'Champion Bonus': The single best match gets a huge boost
        # If it's a near-duplicate (>0.90), it SHOULD win.
        if i == 0:
            if score > 0.90:
                score += 10.0  # Massive bonus: 1-NN override
            else:
                score += 2.0   # Moderate bonus: priority
            
        disease_votes[disease] += score

        similar_cases.append({
            "image_path": image_paths[idx],
            "disease": disease,
            "similarity": float(sim)
        })

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


def analyze_skin_image(image_path: str):
    image = Image.open(image_path).convert("RGB")
    cls_emb, mean_emb = embed_image(image)

    # Method 1: CLS + Rank-Weighted kNN
    m1_ranks, m1_cases = knn_vote(cls_emb, cls_index)
    
    # Method 3: Mean + Rank-Weighted kNN (Done first to reuse neighbors for M2)
    m3_ranks, m3_cases = knn_vote(mean_emb, mean_index)
    
    # Method 2: Mean + Cosine Similarity (Centroids)
    m2_ranks = cosine_centroid_search(mean_emb)
    
    # Find "Supporting Evidence" for Method 2 (Top Centroid Disease matches from M3 search)
    m2_cases = []
    top_centroid_disease = m2_ranks[0][0]
    for case in m3_cases:
        if case['disease'] == top_centroid_disease:
            m2_cases.append(case)
            if len(m2_cases) >= 5: break

    return {
        "cls_knn": {
            "top_diseases": m1_ranks[:TOP_DISEASES],
            "similar_cases": m1_cases[:5]
        },
        "mean_cosine": {
            "top_diseases": m2_ranks,
            "similar_cases": m2_cases  # New: Supporting evidence
        },
        "mean_knn": {
            "top_diseases": m3_ranks[:TOP_DISEASES],
            "similar_cases": m3_cases[:5]
        }
    }
