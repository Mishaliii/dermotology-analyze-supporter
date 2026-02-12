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
image_labels = np.load(
    os.path.join(EMBEDDING_DIR, "image_labels.npy"),
    allow_pickle=True
)
image_paths = np.load(
    os.path.join(EMBEDDING_DIR, "image_paths.npy"),
    allow_pickle=True
)

faiss_index = faiss.read_index(
    os.path.join(EMBEDDING_DIR, "image_index.faiss")
)

# =============================
# CORE FUNCTIONS
# =============================

def embed_image(image: Image.Image) -> np.ndarray:
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).cpu().numpy()


def knn_vote(query_embedding: np.ndarray):
    """
    KNN voting using FAISS similarity scores
    """
    q = query_embedding.copy()
    faiss.normalize_L2(q)

    scores, indices = faiss_index.search(q, KNN_K)

    disease_votes = defaultdict(float)
    similar_cases = []

    for sim, idx in zip(scores[0], indices[0]):
        disease = image_labels[idx]
        disease_votes[disease] += float(sim)

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


def analyze_skin_image(image_path: str):
    image = Image.open(image_path).convert("RGB")
    embedding = embed_image(image)

    ranked_diseases, similar_cases = knn_vote(embedding)

    top_diseases = ranked_diseases[:TOP_DISEASES]

    decision_type = "single"
    if len(top_diseases) > 1:
        score_gap = top_diseases[0][1] - top_diseases[1][1]
        if score_gap < 0.05:
            decision_type = "ambiguous"

    return {
        "decision": {
            "type": decision_type,
            "diseases": [d for d, _ in top_diseases]
        },
        "votes": top_diseases,
        "similar_cases": similar_cases[:5]
    }
