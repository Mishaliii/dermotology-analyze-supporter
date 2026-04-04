from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

import shutil
import os
import sys
import uuid
import time
import re
import threading

# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

sys.path.append(SCRIPTS_DIR)

try:
    from scripts.pipeline import analyze_skin_image, load_models
    from scripts.scoring import get_fastsam_model, get_calibration_data, get_visual_score
    from scripts.prescription import (
        create_case, search_medicines, generate_treatment_suggestions, 
        save_prescription, get_doctor_cases, get_patient_history, get_prescription, add_medicine,
        get_db_connection, search_patients, create_patient
    )
    from scripts.auth import (
        signup_doctor,
        login_doctor,
        get_pending_doctors,
        approve_doctor,
        reject_doctor,
        list_doctors,
        create_doctor_by_admin,
        update_doctor_by_admin,
        delete_doctor_by_admin,
    )
except ImportError:
    from pipeline import analyze_skin_image, load_models
    from scoring import get_fastsam_model, get_calibration_data, get_visual_score
    from prescription import (
        create_case, search_medicines, generate_treatment_suggestions, 
        save_prescription, get_doctor_cases, get_patient_history, get_prescription, add_medicine,
        get_db_connection, search_patients, create_patient
    )
    from auth import (
        signup_doctor,
        login_doctor,
        get_pending_doctors,
        approve_doctor,
        reject_doctor,
        list_doctors,
        create_doctor_by_admin,
        update_doctor_by_admin,
        delete_doctor_by_admin,
    )

from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class CaseCreateReq(BaseModel):
    doctor_id: int = 0
    patient_id: int = 0
    image_path: str = ""
    predicted_disease_id: int = 0
    predicted_disease_name: str = "" 
    confirmed_disease_id: int = 0
    confirmed_disease_name: str = "" 
    severity_json: dict = {}
    ai_confidence: float = 0.0

class SuggestionReq(BaseModel):
    disease_name: str
    severity_score: int

class RxItem(BaseModel):
    medicine_id: int
    dose: str = ""
    frequency: str = ""
    duration: str = ""
    instructions: str = ""

class SaveRxReq(BaseModel):
    doctor_id: int
    case_id: int
    notes: str = ""
    items: List[RxItem] = []

class AddMedicineReq(BaseModel):
    name: str
    generic_name: str = ""
    category: str = ""
    form: str = ""
    strength: str = ""

class PatientCreateReq(BaseModel):
    doctor_id: int
    name: str
    age: int
    gender: str = ""
    medical_history: str = ""

class SignupReq(BaseModel):
    name: str
    email: str
    password: str
    license_number: str = ""
    clinic_name: str = ""

class LoginReq(BaseModel):
    email: str
    password: str


class AdminActionReq(BaseModel):
    admin_doctor_id: int
    doctor_id: int


class AdminCreateDoctorReq(BaseModel):
    admin_doctor_id: int
    name: str
    email: str
    password: str
    license_number: str = ""
    clinic_name: str = ""
    is_admin: bool = False
    approved: bool = True


class AdminUpdateDoctorReq(BaseModel):
    admin_doctor_id: int
    name: str
    email: str
    license_number: str = ""
    clinic_name: str = ""
    is_admin: bool = False
    approved: bool = True
    password: str = ""


class ReviewApproveReq(BaseModel):
    admin_doctor_id: int
    disease_name: str


class ReviewRejectReq(BaseModel):
    admin_doctor_id: int
    notes: str = ""


# --------------------------------------------------
# FASTAPI INIT
# --------------------------------------------------

app = FastAPI(
    title="Clinical Dermatology Decision Support",
    description="AI-powered dermatology similarity analysis",
    version="1.0"
)


AI_ASSETS_READY = False
AI_ASSETS_LOADING = False
AI_ASSETS_ERROR = ""
_ai_assets_lock = threading.Lock()
_score_cache_lock = threading.Lock()
_score_cache: Dict[str, Dict[str, Any]] = {}


def _load_ai_assets_once() -> None:
    """Load heavy AI assets exactly once in a thread-safe way."""
    global AI_ASSETS_READY, AI_ASSETS_LOADING, AI_ASSETS_ERROR

    if AI_ASSETS_READY:
        return

    with _ai_assets_lock:
        if AI_ASSETS_READY:
            return

        AI_ASSETS_LOADING = True
        AI_ASSETS_ERROR = ""
        start = time.perf_counter()

        try:
            print("[WARMUP] Loading DINOv2 + FAISS index...")
            load_models()
            print("[WARMUP] DINOv2 + FAISS ready")

            print("[WARMUP] Loading calibration + FastSAM...")
            get_calibration_data()
            get_fastsam_model()
            print("[WARMUP] FastSAM ready")

            # Prime the severity stack once so the first clinical scoring call is faster.
            try:
                import numpy as np
                import cv2

                warmup_image_path = os.path.join(TEMP_DIR, "_warmup_sample.jpg")
                if not os.path.exists(warmup_image_path):
                    dummy = np.full((256, 256, 3), 180, dtype=np.uint8)
                    cv2.imwrite(warmup_image_path, dummy)

                get_visual_score(warmup_image_path, "acne")
                print("[WARMUP] Severity scoring pipeline primed")
            except Exception as prime_exc:
                print(f"[WARMUP] Severity prime skipped: {prime_exc}")

            AI_ASSETS_READY = True
            print(f"[WARMUP] AI assets completed in {time.perf_counter() - start:.2f}s")
        except Exception as exc:
            AI_ASSETS_ERROR = str(exc)
            print(f"[WARMUP] AI asset loading failed: {exc}")
        finally:
            AI_ASSETS_LOADING = False


@app.on_event("startup")
def warmup_models_on_startup():
    """
    Start quickly, then preload heavy AI assets in background.
    """
    try:
        ensure_review_queue_table()
        print("[WARMUP] Review queue table ready")
    except Exception as exc:
        print(f"[WARMUP] Review queue setup skipped: {exc}")

    # Launch model loading in background so API is available immediately.
    thread = threading.Thread(target=_load_ai_assets_once, daemon=True)
    thread.start()
    print("[WARMUP] Background AI warmup started")

# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# DIRECTORIES
# --------------------------------------------------

FRONTEND_DIR = os.path.join(ROOT_DIR, "Frontend")
FRONTEND_DIST_DIR = os.path.join(FRONTEND_DIR, "dist")
DATA_DIR = os.path.join(ROOT_DIR, "data")
TEMP_DIR = os.path.join(ROOT_DIR, "temp")

os.makedirs(TEMP_DIR, exist_ok=True)

# --------------------------------------------------
# STATIC MOUNTS
# --------------------------------------------------

if os.path.exists(FRONTEND_DIST_DIR):
    frontend_assets = os.path.join(FRONTEND_DIST_DIR, "assets")
    if os.path.exists(frontend_assets):
        app.mount("/assets", StaticFiles(directory=frontend_assets), name="frontend-assets")

if os.path.exists(DATA_DIR):
    app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")
else:
    print("WARNING: data folder missing")

app.mount("/temp", StaticFiles(directory=TEMP_DIR), name="temp")


# --------------------------------------------------
# ROOT PAGE
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home():
    frontend_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(frontend_index):
        return FileResponse(frontend_index)

    return "<h2>Frontend not built. Run: cd Frontend && npm install && npm run build</h2>"

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)  # No Content — silences browser 404 logs


# --------------------------------------------------
# AUTH ENDPOINTS
# --------------------------------------------------

@app.post("/signup")
def api_signup(req: SignupReq):
    return signup_doctor(
        name=req.name,
        email=req.email,
        password=req.password,
        license_number=req.license_number,
        clinic_name=req.clinic_name,
    )

@app.post("/login")
def api_login(req: LoginReq):
    return login_doctor(email=req.email, password=req.password)


@app.get("/health/models")
def api_models_health():
    return {
        "success": True,
        "ready": AI_ASSETS_READY,
        "loading": AI_ASSETS_LOADING,
        "error": AI_ASSETS_ERROR,
    }


@app.get("/admin/pending_doctors")
def api_get_pending_doctors(admin_doctor_id: int):
    return get_pending_doctors(admin_doctor_id)


@app.post("/admin/approve_doctor")
def api_approve_doctor(req: AdminActionReq):
    return approve_doctor(req.admin_doctor_id, req.doctor_id)


@app.post("/admin/reject_doctor")
def api_reject_doctor(req: AdminActionReq):
    return reject_doctor(req.admin_doctor_id, req.doctor_id)


@app.get("/admin/doctors")
def api_list_doctors(admin_doctor_id: int):
    return list_doctors(admin_doctor_id)


@app.post("/admin/doctors")
def api_create_doctor(req: AdminCreateDoctorReq):
    return create_doctor_by_admin(
        admin_doctor_id=req.admin_doctor_id,
        name=req.name,
        email=req.email,
        password=req.password,
        license_number=req.license_number,
        clinic_name=req.clinic_name,
        is_admin=req.is_admin,
        approved=req.approved,
    )


@app.put("/admin/doctors/{doctor_id}")
def api_update_doctor(doctor_id: int, req: AdminUpdateDoctorReq):
    return update_doctor_by_admin(
        admin_doctor_id=req.admin_doctor_id,
        doctor_id=doctor_id,
        name=req.name,
        email=req.email,
        license_number=req.license_number,
        clinic_name=req.clinic_name,
        is_admin=req.is_admin,
        approved=req.approved,
        password=req.password,
    )


@app.delete("/admin/doctors/{doctor_id}")
def api_delete_doctor(doctor_id: int, admin_doctor_id: int):
    return delete_doctor_by_admin(admin_doctor_id, doctor_id)


@app.get("/admin/doctors/{doctor_id}/patients")
def api_admin_doctor_patients(doctor_id: int, admin_doctor_id: int):
    if not is_admin_doctor(admin_doctor_id):
        return {"success": False, "error": "Admin access required.", "patients": []}

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.id, p.name, p.age, p.gender, p.medical_history
                    FROM doctor_patients dp
                    JOIN patients p ON p.id = dp.patient_id
                    WHERE dp.doctor_id = %s
                    ORDER BY p.name ASC
                    """,
                    (doctor_id,),
                )
                rows = cur.fetchall()

        return {
            "success": True,
            "patients": [
                {
                    "id": r[0],
                    "name": r[1] or "",
                    "age": r[2] or 0,
                    "gender": r[3] or "",
                    "contact": r[4] or "",
                }
                for r in rows
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e), "patients": []}


@app.get("/admin/review_queue")
def api_review_queue(admin_doctor_id: int):
    if not is_admin_doctor(admin_doctor_id):
        return {"success": False, "error": "Admin access required.", "items": []}

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                      SELECT id, image_path, suggested_disease, confidence, reason, status, confirmed_disease,
                          resolved_path, notes, created_at, reviewed_at, image_hash, COALESCE(is_existing, FALSE)
                    FROM analysis_review_queue
                    ORDER BY
                        CASE
                            WHEN status = 'pending' AND COALESCE(is_existing, FALSE) = FALSE THEN 0
                            WHEN status = 'known' OR COALESCE(is_existing, FALSE) = TRUE THEN 1
                            WHEN status = 'approved' THEN 2
                            WHEN status = 'rejected' THEN 3
                            ELSE 4
                        END,
                        created_at DESC
                    LIMIT 200
                    """
                )
                rows = cur.fetchall()

        items = [
            {
                "id": r[0],
                "image_path": r[1] or "",
                "suggested_disease": r[2] or "",
                "confidence": float(r[3] or 0.0),
                "reason": r[4] or "",
                "status": r[5] or "pending",
                "confirmed_disease": r[6] or "",
                "resolved_path": r[7] or "",
                "notes": r[8] or "",
                "created_at": str(r[9]) if r[9] else "",
                "reviewed_at": str(r[10]) if r[10] else "",
                "image_hash": r[11] or "",
                "is_existing": bool(r[12]),
            }
            for r in rows
        ]
        return {"success": True, "items": items}
    except Exception as e:
        return {"success": False, "error": str(e), "items": []}


@app.post("/admin/review_queue/{review_id}/approve")
def api_review_approve(review_id: int, req: ReviewApproveReq):
    if not is_admin_doctor(req.admin_doctor_id):
        return {"success": False, "error": "Admin access required."}

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT image_path FROM analysis_review_queue WHERE id = %s AND status = 'pending'",
                    (review_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {"success": False, "error": "Review item not found."}

                image_path = row[0] or ""
                fs_path = image_path
                if image_path.startswith("/temp/"):
                    fs_path = os.path.join(TEMP_DIR, image_path[len("/temp/"):])
                elif image_path.startswith("/"):
                    fs_path = os.path.join(ROOT_DIR, image_path.lstrip("/"))

                folder_name = normalize_disease_folder(req.disease_name)
                target_dir = os.path.join(DATA_DIR, "ISD-198", "Train", folder_name)
                os.makedirs(target_dir, exist_ok=True)
                filename = os.path.basename(fs_path)
                target_path = os.path.join(target_dir, filename)

                if os.path.exists(fs_path):
                    shutil.copy2(fs_path, target_path)

                cur.execute(
                    """
                    UPDATE analysis_review_queue
                    SET status = 'approved',
                        confirmed_disease = %s,
                        resolved_path = %s,
                        reviewed_by = %s,
                        reviewed_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (req.disease_name, target_path.replace("\\", "/"), req.admin_doctor_id, review_id),
                )
            conn.commit()

        return {"success": True, "saved_path": target_path.replace("\\", "/")}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/admin/review_queue/{review_id}/reject")
def api_review_reject(review_id: int, req: ReviewRejectReq):
    if not is_admin_doctor(req.admin_doctor_id):
        return {"success": False, "error": "Admin access required."}

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE analysis_review_queue
                    SET status = 'rejected',
                        notes = %s,
                        reviewed_by = %s,
                        reviewed_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND status = 'pending'
                    """,
                    (req.notes or "", req.admin_doctor_id, review_id),
                )
                updated = cur.rowcount
            conn.commit()

        if not updated:
            return {"success": False, "error": "Review item not found."}
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --------------------------------------------------
# PATIENT ENDPOINTS
# --------------------------------------------------

@app.get("/patients/search")
def api_search_patients(doctor_id: int, q: str = ""):
    """Search patients linked to this doctor by name."""
    try:
        return {"success": True, "patients": search_patients(doctor_id, q)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/patients/create")
def api_create_patient(req: PatientCreateReq):
    """Create a new patient and link to the doctor."""
    return create_patient(
        doctor_id=req.doctor_id,
        name=req.name,
        age=req.age,
        gender=req.gender,
        medical_history=req.medical_history,
    )

@app.get("/patients/history")
def api_patient_history(patient_id: int, doctor_id: int):
    """Get chronological history of a patient's visits, diagnoses, and severities."""
    try:
        if not doctor_has_patient_access(doctor_id, patient_id):
            return {"success": False, "error": "You do not have permission to view this patient history.", "history": []}
        return {"success": True, "history": get_patient_history(patient_id)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def cleanup_old_files(directory, age_minutes=60):
    """
    Deletes files in `directory` older than `age_minutes`.
    This prevents disk clutter while keeping recent previews.
    """
    current_time = time.time()
    age_seconds = age_minutes * 60
    
    if not os.path.exists(directory):
        return

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > age_seconds:
                    os.remove(file_path)
                    print(f"[CLEANUP] Deleted old file: {filename}")
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")


def ensure_review_queue_table():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_review_queue (
                    id SERIAL PRIMARY KEY,
                    image_path TEXT NOT NULL,
                    suggested_disease TEXT,
                    confidence REAL,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    confirmed_disease TEXT,
                    resolved_path TEXT,
                    reviewed_by INTEGER REFERENCES doctors(id),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP
                );
                """
            )
        conn.commit()


def is_admin_doctor(doctor_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(is_admin, FALSE) FROM doctors WHERE id = %s", (doctor_id,))
                row = cur.fetchone()
                return bool(row and row[0])
    except Exception:
        return False


def doctor_has_patient_access(doctor_id: int, patient_id: int) -> bool:
    if doctor_id <= 0 or patient_id <= 0:
        return False
    if is_admin_doctor(doctor_id):
        return True
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM doctor_patients
                    WHERE doctor_id = %s AND patient_id = %s
                    LIMIT 1
                    """,
                    (doctor_id, patient_id),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def doctor_has_case_access(doctor_id: int, case_id: int) -> bool:
    if doctor_id <= 0 or case_id <= 0:
        return False
    if is_admin_doctor(doctor_id):
        return True
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM cases
                    WHERE id = %s AND doctor_id = %s
                    LIMIT 1
                    """,
                    (case_id, doctor_id),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def _score_cache_key(image_path: str, disease_name: str) -> str:
    return f"{(image_path or '').strip()}|{(disease_name or '').strip().lower()}"


def _cache_severity_metrics(image_path: str, disease_name: str, metrics: Dict[str, Any]) -> None:
    key = _score_cache_key(image_path, disease_name)
    with _score_cache_lock:
        _score_cache[key] = metrics


def _get_cached_severity_metrics(image_path: str, disease_name: str) -> Optional[Dict[str, Any]]:
    key = _score_cache_key(image_path, disease_name)
    with _score_cache_lock:
        return _score_cache.get(key)


def _prefetch_top_disease_score(image_web_path: str, disease_name: str) -> None:
    """Best-effort async precompute to reduce first-open severity latency."""
    try:
        fs_path = image_web_path
        if fs_path.startswith("/temp/"):
            fs_path = os.path.join(TEMP_DIR, fs_path[len("/temp/"):])
        elif fs_path.startswith("/"):
            fs_path = os.path.join(ROOT_DIR, fs_path.lstrip("/"))

        if not os.path.exists(fs_path):
            return

        metrics = get_visual_score(fs_path, disease_name)
        if isinstance(metrics, dict) and metrics:
            _cache_severity_metrics(image_web_path, disease_name, metrics)
    except Exception as exc:
        print(f"[SEVERITY_PREFETCH] skipped: {exc}")


def queue_analysis_for_review(image_path: str, suggested_disease: str, confidence: float, reason: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analysis_review_queue (image_path, suggested_disease, confidence, reason, status)
                    VALUES (%s, %s, %s, %s, 'pending')
                    """,
                    (image_path, suggested_disease, confidence, reason),
                )
            conn.commit()
    except Exception as exc:
        print(f"[REVIEW_QUEUE] enqueue skipped: {exc}")


def normalize_disease_folder(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\- ]+", "", (name or "").strip())
    return cleaned.replace(" ", "_") or "Unknown"


# --------------------------------------------------
# ANALYZE ENDPOINT
# --------------------------------------------------

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...)
):
    # Do not block request threads while warmup is running.
    if not AI_ASSETS_READY:
        if AI_ASSETS_LOADING:
            return {
                "error": "Clinical analysis service is still initializing. Please retry in about 30-60 seconds.",
                "loading": True,
            }
        _load_ai_assets_once()
        if not AI_ASSETS_READY:
            return {"error": AI_ASSETS_ERROR or "Clinical analysis service is not ready yet. Please retry shortly."}

    # ---------- Auto Cleanup (Lazy) ----------
    # Delete files older than 60 minutes
    cleanup_old_files(TEMP_DIR, age_minutes=60)

    # ---------- Save Uploaded Image ----------
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    temp_path = os.path.join(TEMP_DIR, unique_name)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        print(f"[INFO] Analyzing image: {temp_path}")

        # ---------- RUN AI PIPELINE ----------
        results = analyze_skin_image(temp_path)

        # ---------- Normalize Paths for Browser ----------
        for method_name, method_result in results.items():

            if not isinstance(method_result, dict):
                continue

            for case in method_result.get("similar_cases", []):

                raw_path = case["image_path"]

                web_path = raw_path.replace("\\", "/")

                if web_path.startswith("./"):
                    web_path = web_path[2:]

                if not web_path.startswith("/"):
                    web_path = "/" + web_path

                case["web_url"] = web_path
                case["filename"] = os.path.basename(raw_path)

        # ---------- Send Uploaded Image URL ----------
        uploaded_web_path = f"/temp/{unique_name}"
        results["uploaded_image"] = uploaded_web_path

        # Queue low-confidence or unknown analyses for admin review.
        try:
            suggested_disease = "Unknown"
            confidence = 0.0
            cls_knn = results.get("cls_knn") if isinstance(results, dict) else None
            if isinstance(cls_knn, dict):
                top = cls_knn.get("top_diseases") or []
                if top and isinstance(top[0], (list, tuple)) and len(top[0]) >= 2:
                    suggested_disease = str(top[0][0])
                    confidence = float(top[0][1] or 0.0)

            if confidence < 0.60:
                queue_analysis_for_review(
                    image_path=uploaded_web_path,
                    suggested_disease=suggested_disease,
                    confidence=confidence,
                    reason="Low confidence analysis requires admin dataset review",
                )

            # Precompute severity for the candidate diagnoses in the background.
            candidate_diseases = []
            if isinstance(cls_knn, dict):
                top = cls_knn.get("top_diseases") or []
                candidate_diseases = [str(item[0]) for item in top if isinstance(item, (list, tuple)) and item and str(item[0]).strip()]
            elif suggested_disease and suggested_disease != "Unknown":
                candidate_diseases = [suggested_disease]

            for disease_name in candidate_diseases[:4]:
                threading.Thread(
                    target=_prefetch_top_disease_score,
                    args=(uploaded_web_path, disease_name),
                    daemon=True,
                ).start()
        except Exception as queue_exc:
            print(f"[REVIEW_QUEUE] failed to evaluate queue condition: {queue_exc}")

        return results

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

    finally:
        # NOTE:
        # We DO NOT delete temp immediately,
        # otherwise preview disappears.
        pass


# --------------------------------------------------
# ON-DEMAND DISEASE SCORING ENDPOINT
# --------------------------------------------------

class ScoreDiseaseReq(BaseModel):
    image_path: str
    disease_name: str

@app.post("/score_disease")
def api_score_disease(req: ScoreDiseaseReq):
    """
    Lazily scores a single disease on-demand when the user clicks a disease chip.
    Keeps the initial /analyze response fast by deferring non-top disease scoring.
    """
    try:
        if not AI_ASSETS_READY:
            if AI_ASSETS_LOADING:
                return {"success": False, "loading": True, "error": "Severity service is still initializing. Please retry in about 30-60 seconds."}
            _load_ai_assets_once()
            if not AI_ASSETS_READY:
                return {"success": False, "error": AI_ASSETS_ERROR or "Severity service is not ready yet."}

        cached = _get_cached_severity_metrics(req.image_path, req.disease_name)
        if cached:
            return {"success": True, "disease": req.disease_name, "metrics": cached, "cached": True}

        # image_path is the /temp/... web path — convert to filesystem path
        fs_path = req.image_path
        if fs_path.startswith("/temp/"):
            fs_path = os.path.join(TEMP_DIR, fs_path[len("/temp/"):])
        elif fs_path.startswith("/"):
            fs_path = os.path.join(ROOT_DIR, fs_path.lstrip("/"))

        if not os.path.exists(fs_path):
            return {"success": False, "error": "Image is no longer available. Please upload again."}
        
        metrics = get_visual_score(fs_path, req.disease_name)
        if not isinstance(metrics, dict) or not metrics:
            return {
                "success": False,
                "error": "AI severity assessment could not be generated for this image. Please score manually.",
            }
        _cache_severity_metrics(req.image_path, req.disease_name, metrics)
        return {"success": True, "disease": req.disease_name, "metrics": metrics}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# --------------------------------------------------
# CDSS CLINICAL WORKFLOW ENDPOINTS
# --------------------------------------------------

@app.post("/create_case")
def api_create_case(req: CaseCreateReq):
    try:
        if req.doctor_id <= 0 or req.patient_id <= 0:
            return {"success": False, "error": "Invalid doctor or patient for case creation."}

        if not doctor_has_patient_access(req.doctor_id, req.patient_id):
            return {"success": False, "error": "You do not have permission to create a case for this patient."}

        # Resolve predicted_disease_name to ID
        p_id = req.predicted_disease_id
        if p_id == 0 and req.predicted_disease_name:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM diseases WHERE lower(name) = lower(%s)", (req.predicted_disease_name,))
                    res = cur.fetchone()
                    if res:
                        p_id = res[0]
                    else:
                        return {"success": False, "error": f"Predicted disease '{req.predicted_disease_name}' is not recognized."}
                    
        # Resolve confirmed_disease_name to ID
        c_id = req.confirmed_disease_id
        if c_id == 0 and req.confirmed_disease_name:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM diseases WHERE lower(name) = lower(%s)", (req.confirmed_disease_name,))
                    res = cur.fetchone()
                    if res:
                        c_id = res[0]
                    else:
                        return {"success": False, "error": f"Confirmed disease '{req.confirmed_disease_name}' is not recognized."}

        if p_id == 0 or c_id == 0:
            return {"success": False, "error": "Disease selection is required before creating a case."}

        case_info = create_case(
            doctor_id=req.doctor_id,
            patient_id=req.patient_id,
            image_path=req.image_path,
            predicted_disease_id=p_id,
            confirmed_disease_id=c_id,
            severity_json=req.severity_json,
            ai_confidence=req.ai_confidence
        )
        return {
            "success": True, 
            "case_id": case_info["case_id"],
            "doctor_name": case_info["doctor_name"],
            "patient_name": f"{case_info['patient_name']} ({case_info['patient_age']} y/o)"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/medicines")
def api_search_medicines(search: str = "", disease: str = ""):
    return search_medicines(search, disease)

@app.post("/medicine/add")
def api_add_medicine(req: AddMedicineReq):
    try:
        res = add_medicine(req.name, req.generic_name, req.category, req.form, req.strength)
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/treatment_suggestions")
def api_treatment_suggestions_get(disease: str, severity: int):
    try:
        suggestions = generate_treatment_suggestions(disease, severity)
        return {"success": True, "suggestions": suggestions}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/generate_prescription")
def api_generate_prescription(req: SuggestionReq):
    try:
        suggestions = generate_treatment_suggestions(req.disease_name, req.severity_score)
        return {"success": True, "suggestions": suggestions}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/save_prescription")
def api_save_prescription(req: SaveRxReq):
    try:
        if not doctor_has_case_access(req.doctor_id, req.case_id):
            return {"success": False, "error": "You do not have permission to save this prescription."}
        rx_id = save_prescription(req.case_id, req.notes, [i.model_dump() for i in req.items])
        return {"success": True, "prescription_id": rx_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/doctor_cases/{doctor_id}")
def api_get_doctor_cases(doctor_id: int):
    return get_doctor_cases(doctor_id)

@app.get("/patient_history/{patient_id}")
def api_get_patient_history(patient_id: int, doctor_id: int):
    if not doctor_has_patient_access(doctor_id, patient_id):
        return {"success": False, "error": "You do not have permission to view this patient history."}
    return get_patient_history(patient_id)

@app.get("/case/{case_id}/prescription")
def api_get_prescription(case_id: int, doctor_id: int):
    if not doctor_has_case_access(doctor_id, case_id):
        return {"success": False, "error": "You do not have permission to view this prescription."}
    rx = get_prescription(case_id)
    if rx:
        return {"success": True, "prescription": rx}
    return {"success": False, "error": "Prescription not found"}


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """
    Serves Vite SPA routes directly from FastAPI in production.
    Non-frontend paths are left to dedicated API/static routes.
    """
    blocked_prefixes = ("api", "temp", "data", "assets")
    if any(full_path.startswith(prefix) for prefix in blocked_prefixes):
        return HTMLResponse("Not Found", status_code=404)

    frontend_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(frontend_index):
        return FileResponse(frontend_index)

    return HTMLResponse("Frontend not available", status_code=404)


# --------------------------------------------------
# RUN SERVER
# --------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
