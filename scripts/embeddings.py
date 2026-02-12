import os
import torch
import numpy as np
from PIL import Image
from tqdm import tqdm
from transformers import AutoImageProcessor, AutoModel

# =============================
# CONFIG
# =============================
DATA_DIR = "data/ISD-198/Train"
OUTPUT_DIR = "embeddings"
MODEL_NAME = "facebook/dinov2-base"
DEVICE = "cpu"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================
# LOAD MODEL
# =============================
processor = AutoImageProcessor.from_pretrained(MODEL_NAME, use_fast=False)
model = AutoModel.from_pretrained(MODEL_NAME)
model.eval().to(DEVICE)
torch.set_grad_enabled(False)

# =============================
# STORAGE
# =============================
embeddings = []
labels = []
paths = []

# =============================
# EMBEDDING EXTRACTION
# =============================
for disease in sorted(os.listdir(DATA_DIR)):
    disease_path = os.path.join(DATA_DIR, disease)
    if not os.path.isdir(disease_path):
        continue

    print(f"\nProcessing disease: {disease}")

    for img_name in tqdm(os.listdir(disease_path)):
        img_path = os.path.join(disease_path, img_name)

        if not img_name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        try:
            image = Image.open(img_path).convert("RGB")
        except:
            continue

        inputs = processor(images=image, return_tensors="pt")
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            emb = outputs.last_hidden_state.mean(dim=1)

        embeddings.append(emb.cpu().numpy())
        labels.append(disease)
        paths.append(img_path)

# =============================
# SAVE
# =============================
embeddings = np.vstack(embeddings)

np.save(os.path.join(OUTPUT_DIR, "image_embeddings.npy"), embeddings)
np.save(os.path.join(OUTPUT_DIR, "image_labels.npy"), np.array(labels))
np.save(os.path.join(OUTPUT_DIR, "image_paths.npy"), np.array(paths))

print("✅ Embeddings saved:", embeddings.shape)
