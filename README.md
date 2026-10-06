# Dermatology Decision Support System (DDSS)

An AI-assisted clinical decision-support **prototype** for dermatology. Instead of returning a single opaque label, it retrieves visually similar historical cases, ranks candidate conditions from that evidence, and lets the clinician confirm the diagnosis before severity scoring, case storage, and prescription drafting.

> **Demo video:** 

https://github.com/user-attachments/assets/26dd698a-91c4-4e15-a29f-7250bfc95aa8

]
>
> **Status:** Research / portfolio prototype. Not clinically validated and not a diagnostic device.

---

## Why retrieval instead of a classifier?

A standard classifier outputs *"Acne, 82%"* with no way to check the reasoning. This system outputs:

- the most visually similar reference images, with similarity scores
- several candidate conditions with weighted evidence
- a clinician confirmation step
- a disease-specific severity calculator
- a stored case and treatment/prescription workflow

The clinician can see *what the suggestion is based on*, which makes the output easier to question and trust appropriately.

---

## Clinician workflow

1. Doctor signs in (admin-approved accounts)
2. Select or create a patient
3. Upload a skin image
4. Review similar cases and ranked disease candidates
5. Confirm the likely condition
6. Run the disease-specific severity calculator
7. Save the case, review treatment suggestions, generate a prescription

*(Add screenshots here: login, patient list, analysis results, severity, prescription.)*

---

## Architecture

```text
React / TypeScript (Vite)
        |  HTTP JSON + multipart
        v
FastAPI backend
   |-- DINOv2 embedding (3-view test-time augmentation)
   |-- FAISS similarity search ---> PostgreSQL (image + disease metadata)
   |-- FastSAM + OpenCV severity pipeline
   '-- PostgreSQL clinical records (patients, cases, prescriptions)
```

### Retrieval pipeline

| Step | Detail |
|---|---|
| Model | `facebook/dinov2-base` (self-supervised ViT), CPU inference |
| Query views | Resized original, horizontal flip, 90% center zoom |
| Representation | CLS token, 768-dim, averaged over the 3 views |
| Normalization | L2-normalized, so inner product is cosine similarity |
| Index | FAISS `IndexFlatIP` over the reference corpus |
| Search | Top 50 neighbors retrieved, top 15 used for voting |
| Ranking | Similarity-weighted disease voting with a top-match bonus |
| Output | 2 to 5 candidate diseases, up to 30 similar cases |
| Metadata | FAISS IDs resolved to image path and disease via PostgreSQL |

### Severity analysis

FastSAM segmentation plus OpenCV features (lesion coverage, region count, texture, redness, edge proxy) feed heuristic, disease-specific scales:

- Psoriasis: PASI-style
- Acne: GAGS-style
- Eczema: EASI-style
- Vitiligo: VASI-style
- Moles / melanoma: ABCDE-style
- Alopecia: SALT-style

These are image-based approximations, not validated clinical scores.

---

## Tech stack

- **Frontend:** React 18, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS, Radix UI, Framer Motion
- **Backend:** FastAPI, Uvicorn, Pydantic, psycopg
- **ML / CV:** PyTorch, Hugging Face Transformers, FAISS (CPU), Ultralytics FastSAM, OpenCV, scikit-image, NumPy, Pillow
- **Database:** PostgreSQL

---

## Design decisions

- **Retrieval over classification:** gives explainable, inspectable evidence and avoids training a classification head on a small dataset.
- **CLS token with test-time augmentation:** more stable queries than a single view.
- **Deferred severity scoring:** severity runs in a separate `/score_disease` call so the first results appear quickly on CPU.
- **Background model warmup:** server starts immediately and reports readiness through `/health/models`.
- **Clinician in the loop:** the system never auto-confirms a diagnosis.

---

## Limitations (honest)

- Not clinically validated; no formal accuracy evaluation is included
- Severity scores are heuristic
- Reference corpus is limited to a research dataset (ISD-198), so rare conditions and diverse skin tones are under-represented
- Prototype-level security: no token-based sessions, simple password hashing, permissive CORS. Not production-ready
- Runs on CPU; first request after startup is slow while models load

---

## Running locally

```bash
# Backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:8000

# Frontend
cd Frontend
npm install
npm run dev
```

**Requirements you must supply yourself** (not included in this repository):

- A local PostgreSQL instance and the schema created by `scripts/build_postgres_db.py`
- The reference image dataset, embeddings, and FAISS index (see `scripts/embeddings.py` and `scripts/faiss_index.py`)
- `FastSAM-s.pt`

Python 3.11 was used for development.

---

## Data notice

Reference medical images are **not** distributed with this repository. Please check the license of the source dataset before using or redistributing it.

---

## Roadmap

- Move all configuration to environment variables
- Salted password hashing and token-based auth
- Restrict CORS and public static mounts
- Pin model revisions
- Quantitative evaluation (top-k accuracy on the held-out split)
- Docker-based deployment

---

## Author

**Mishal**: MCA graduate (2026), AI/ML,backend developer adn Fullstack Developer.
[ https://www.linkedin.com/in/muhammedmishal13/ ] | [muhammedmishalkpm13@gmail.com]





