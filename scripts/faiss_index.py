import numpy as np
import faiss
import os

# -----------------------------
# -----------------------------
# LOAD EMBEDDINGS
# -----------------------------
EMBEDDING_DIR = "embeddings"

cls_embeddings = np.load(os.path.join(EMBEDDING_DIR, "cls_embeddings.npy"))
mean_embeddings = np.load(os.path.join(EMBEDDING_DIR, "mean_embeddings.npy"))

print(f"Loaded CLS embeddings: {cls_embeddings.shape}")
print(f"Loaded Mean embeddings: {mean_embeddings.shape}")

# -----------------------------
# BUILD FAISS INDICES
# -----------------------------
def build_and_save_index(embeddings, name):
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    
    output_path = os.path.join(EMBEDDING_DIR, f"{name}_index.faiss")
    faiss.write_index(index, output_path)
    print(f"✅ {name.upper()} index built and saved ({index.ntotal} vectors)")

build_and_save_index(cls_embeddings, "cls")
build_and_save_index(mean_embeddings, "mean")
