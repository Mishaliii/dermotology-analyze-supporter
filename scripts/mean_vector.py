import numpy as np
from collections import defaultdict
import os

# -----------------------------
# LOAD EMBEDDINGS
# -----------------------------
EMBEDDING_DIR = "embeddings"

embeddings = np.load(
    os.path.join(EMBEDDING_DIR, "image_embeddings.npy")
)
labels = np.load(
    os.path.join(EMBEDDING_DIR, "image_labels.npy"),
    allow_pickle=True
)
print("Loaded embeddings:", embeddings.shape)
print("Loaded labels:", len(labels))

# -----------------------------
# GROUP EMBEDDINGS BY DISEASE
# -----------------------------
disease_to_vectors = defaultdict(list)
for emb, label in zip(embeddings, labels):
    disease_to_vectors[label].append(emb)

# -----------------------------
# COMPUTE MEAN VECTOR PER DISEASE
# -----------------------------
disease_mean_vectors = {}
for disease, vectors in disease_to_vectors.items():
    vectors = np.vstack(vectors)
    mean_vector = np.mean(vectors, axis=0)
    disease_mean_vectors[disease] = mean_vector

# -----------------------------
# SAVE MEAN VECTORS
# -----------------------------
output_path = os.path.join(EMBEDDING_DIR, "disease_mean_vectors.npy")
np.save(output_path, disease_mean_vectors)

print("Diseases processed:")
for disease in disease_mean_vectors:
    print(f"- {disease} | Mean vector shape: {disease_mean_vectors[disease].shape}")
