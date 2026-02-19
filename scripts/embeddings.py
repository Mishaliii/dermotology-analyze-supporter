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
cls_embeddings = []
mean_embeddings = []
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

        # Resize (squish) to 224x224 and disable processor's default cropping
        image = image.resize((224, 224))
        inputs = processor(images=image, return_tensors="pt", do_resize=False, do_center_crop=False)
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            # Extract BOTH CLS and Mean
            cls_emb = outputs.last_hidden_state[:, 0, :]
            mean_emb = outputs.last_hidden_state.mean(dim=1)

        cls_embeddings.append(cls_emb.cpu().numpy())
        mean_embeddings.append(mean_emb.cpu().numpy())
        labels.append(disease)
        paths.append(img_path)

# =============================
# SAVE
# =============================
cls_embeddings = np.vstack(cls_embeddings)
mean_embeddings = np.vstack(mean_embeddings)

np.save(os.path.join(OUTPUT_DIR, "cls_embeddings.npy"), cls_embeddings)
np.save(os.path.join(OUTPUT_DIR, "mean_embeddings.npy"), mean_embeddings)
np.save(os.path.join(OUTPUT_DIR, "image_labels.npy"), np.array(labels))
np.save(os.path.join(OUTPUT_DIR, "image_paths.npy"), np.array(paths))

print("Embeddings saved:")
print(f" - CLS Shape: {cls_embeddings.shape}")
print(f" - Mean Shape: {mean_embeddings.shape}")
