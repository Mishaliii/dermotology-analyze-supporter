# Clinical Dermatology Decision Support System

## Project Title
Clinical Dermatology Decision Support System Using Deep Visual Similarity, Severity Scoring, and Prescription Assistance

## Abstract
This project is an AI-assisted clinical dermatology decision support system developed to help doctors analyze skin images, review visually similar historical cases, estimate disease severity, and generate treatment suggestions. The system combines deep image embeddings, FAISS-based similarity search, disease-specific severity heuristics, and a clinical workflow module for patient management, case recording, and prescription generation. It is implemented as a FastAPI web application with a browser-based frontend and PostgreSQL as the clinical data store.

## Problem Statement
Dermatological diagnosis is visually complex and often depends on pattern recognition, clinical severity assessment, and treatment planning. Manual assessment can be time-consuming, especially when comparing similar cases or selecting disease-specific severity scales and medicines. This project addresses that problem by building a system that supports doctors with image-based retrieval, severity estimation, and structured clinical workflow support.

## Main Objective
The main objective of the project is to create an AI-powered dermatology support platform that assists clinicians in:

- analyzing uploaded skin images,
- retrieving visually similar dermatology cases,
- estimating severity using standard dermatology scoring logic,
- managing doctor-patient-case records,
- generating prescription suggestions based on disease and severity,
- storing consultation and prescription history digitally.

## Dataset and Knowledge Base
The system uses the `ISD-198` dermatology image dataset stored locally in the project. Based on the current repository:

- Total disease classes: 198
- Total indexed images: 5,498
- Embedding size: 768 dimensions for each image
- Metadata is maintained through `classes.json`, embedding files, FAISS indices, and PostgreSQL image-to-disease mappings

## Core Technical Idea
This project is primarily a retrieval-based AI system rather than a simple end-to-end classifier. Instead of only predicting one label directly, it converts the uploaded image into a deep visual embedding and compares it against indexed dermatology images. The system then ranks the most similar cases and uses those matches to support diagnosis and clinical review.

## Technology Stack
- Backend: FastAPI, Uvicorn
- Frontend: HTML, CSS, JavaScript
- Database: PostgreSQL with `psycopg`
- Deep Learning: PyTorch, Transformers, DINOv2
- Image Processing: OpenCV, Pillow, scikit-image
- Similarity Search: FAISS
- Segmentation/Region Analysis: FastSAM via Ultralytics

## System Architecture
- Presentation Layer: Web UI for doctor login, patient selection, image upload, scoring, and prescription flow
- Application Layer: FastAPI endpoints for authentication, image analysis, scoring, patient operations, and prescription logic
- AI Layer: DINOv2 embedding generation, FAISS similarity retrieval, FastSAM-assisted lesion analysis, and disease-specific scoring logic
- Data Layer: PostgreSQL tables for doctors, patients, diseases, images, cases, medicines, and prescriptions

## Main Modules Implemented
- Doctor authentication module with signup and login
- Patient management module with patient search, creation, and history view
- Image analysis module for dermatology image upload and retrieval-based diagnosis support
- Disease severity scoring module using PASI, GAGS, EASI, VASI, ABCDE, and SALT-style logic
- Prescription assistance module with medicine lookup, AI suggestions, manual medicine addition, and prescription saving
- Case history and clinical record module for storing consultations and retrieving previous prescriptions

## Image Analysis Pipeline
1. The doctor uploads a skin image through the web interface.
2. The backend saves the file temporarily and removes old temporary files after a fixed time.
3. The uploaded image is converted into a DINOv2 embedding.
4. Test-time augmentation is applied using original, horizontally flipped, and zoomed versions of the image.
5. The embedding is searched against a FAISS index of 5,498 dermatology images.
6. A weighted k-nearest-neighbor voting method is used with `K = 15` and deeper retrieval of `50` neighbors.
7. A champion bonus is applied to the strongest top match to improve rank confidence.
8. The system returns top supporting cases and lets the doctor choose the most clinically appropriate diagnosis.

## Severity Scoring Logic
- Psoriasis: redness, scaling, thickness, and area are estimated to support PASI-style scoring
- Acne: lesion count, coverage, and region-wise distribution are used for GAGS-style scoring
- Eczema/Dermatitis: erythema, edema proxy, excoriation, lichenification, and area are used for EASI-style scoring
- Vitiligo: depigmentation percentage is measured for VASI-style scoring
- Melanoma/Nevus: asymmetry, border, color, and diameter are estimated using ABCDE-inspired heuristics
- Alopecia: hair loss percentage is estimated using SALT-like regional analysis

## Clinical Workflow Implemented
- Doctor logs into the system
- Doctor selects an existing patient or creates a new patient
- Doctor uploads a clinical image
- System shows visually similar supporting cases
- Doctor selects the diagnosis and opens the relevant severity calculator
- System computes or assists with severity scoring
- A case is created in the database with predicted disease, confirmed disease, severity, and AI confidence
- Treatment suggestions are generated based on disease and severity
- Doctor edits medicines if needed, saves prescription, and can print the prescription
- Patient history and previous prescriptions can be viewed later

## Database Design
The project uses the following main database tables:

- `doctors`
- `patients`
- `doctor_patients`
- `diseases`
- `images`
- `cases`
- `medicines`
- `disease_treatments`
- `prescriptions`
- `prescription_items`

## Treatment Suggestion Engine
The treatment module maps diseases to medicines using rule-based severity ranges stored in the database. For example:

- Acne severity ranges map to benzoyl peroxide, adapalene, doxycycline, and isotretinoin
- Psoriasis ranges map to emollients, topical steroids, calcipotriol, methotrexate, and biologics
- Eczema ranges map to emollients, hydrocortisone, tacrolimus, and cyclosporine
- Vitiligo and alopecia also have dedicated medicine rules

## Frontend Features
- Professional login/signup page for doctors
- Patient selection panel with search and new patient creation
- Upload workspace with image preview
- Similar-case evidence panel with similarity percentages
- Interactive disease-specific scoring modal
- Prescription modal with editable medicine rows
- Patient history timeline with prescription viewing
- Print-friendly prescription layout

## Testing and Supporting Scripts
The repository also includes helper scripts for:

- dataset preprocessing,
- embedding extraction,
- FAISS index building,
- PostgreSQL setup and migrations,
- severity calibration,
- medicine import from Excel,
- demo user seeding,
- experimental testing under the `addit` folder.

## Current Strengths of the Project
- Combines AI retrieval and clinical workflow in one system
- Supports real doctor-patient-case-prescription relationships
- Uses standard dermatology severity concepts instead of generic scoring
- Stores consultation history for follow-up care
- Provides explainable evidence through similar historical images

## Current Limitations
- Severity scoring is heuristic and image-based, not a clinically validated diagnostic model
- Some testing scripts are lightweight and not full production-grade automated tests
- Password hashing uses SHA-256 for academic use and should be upgraded for real deployment
- CORS and security configuration are currently permissive for development use
- Some disease support is broader in retrieval than in dedicated severity calculators

## Future Enhancements
- Add stronger authentication and role-based access control
- Improve calibration and validation with dermatologist-reviewed labels
- Expand medicine rules and treatment guideline coverage
- Add report export in PDF format
- Support cloud deployment and mobile capture workflow
- Add clinician feedback loop to improve retrieval relevance over time

## Conclusion
This project successfully implements an end-to-end AI-assisted dermatology decision support platform. It goes beyond simple image classification by combining deep visual similarity retrieval, disease-specific severity scoring, patient record management, and prescription generation in a single clinical workflow. As implemented in the codebase, it is best described as an academic clinical decision support prototype designed to assist, not replace, doctor judgment.
