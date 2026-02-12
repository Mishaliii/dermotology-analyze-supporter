import numpy as np
import faiss
import os

# -----------------------------
# LOAD EMBEDDINGS
# -----------------------------
EMBEDDING_DIR = "embeddings"

embeddings = np.load(
    os.path.join(EMBEDDING_DIR, "image_embeddings.npy")
)
print("Loaded embeddings:", embeddings.shape)

# -----------------------------
# BUILD FAISS INDEX
# -----------------------------
dim = embeddings.shape[1]
index = faiss.IndexFlatIP(dim)  # Inner Product (cosine-ready)

faiss.normalize_L2(embeddings)
index.add(embeddings)

# -----------------------------
# SAVE INDEX
# -----------------------------
faiss.write_index(index, os.path.join(EMBEDDING_DIR, "image_index.faiss"))
print("✅ FAISS index built and saved")
print("Total vectors:", index.ntotal)
