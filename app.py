from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

import shutil
import os
import sys
import uuid
import time

# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

sys.path.append(SCRIPTS_DIR)

try:
    from scripts.pipeline import analyze_skin_image, load_models
    from scripts.scoring import get_fastsam_model, get_calibration_data
    from scripts.prescription import (
        create_case, search_medicines, generate_treatment_suggestions, 
        save_prescription, get_doctor_cases, get_patient_history, get_prescription, add_medicine,
        get_db_connection, search_patients, create_patient
    )
    from scripts.auth import signup_doctor, login_doctor
except ImportError:
    from pipeline import analyze_skin_image, load_models
    from scoring import get_fastsam_model, get_calibration_data
    from prescription import (
        create_case, search_medicines, generate_treatment_suggestions, 
        save_prescription, get_doctor_cases, get_patient_history, get_prescription, add_medicine,
        get_db_connection, search_patients, create_patient
    )
    from auth import signup_doctor, login_doctor

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


# --------------------------------------------------
# FASTAPI INIT
# --------------------------------------------------

app = FastAPI(
    title="Clinical Dermatology Decision Support",
    description="AI-powered dermatology similarity analysis",
    version="1.0"
)


@app.on_event("startup")
def warmup_models_on_startup():
    """
    Preload heavy AI assets once at app startup so the first user upload is responsive.
    """
    start = time.perf_counter()
    try:
        print("[WARMUP] Loading DINOv2 + FAISS index...")
        load_models()
        print("[WARMUP] DINOv2 + FAISS ready")
    except Exception as exc:
        print(f"[WARMUP] DINOv2/FAISS preload skipped: {exc}")

    try:
        print("[WARMUP] Loading calibration + FastSAM...")
        get_calibration_data()
        get_fastsam_model()
        print("[WARMUP] FastSAM ready")
    except Exception as exc:
        print(f"[WARMUP] FastSAM preload skipped: {exc}")

    print(f"[WARMUP] Completed in {time.perf_counter() - start:.2f}s")

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

STATIC_DIR = os.path.join(ROOT_DIR, "static")
DATA_DIR = os.path.join(ROOT_DIR, "data")
TEMP_DIR = os.path.join(ROOT_DIR, "temp")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# --------------------------------------------------
# STATIC MOUNTS
# --------------------------------------------------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return "<h2>Frontend not found. Create static/index.html</h2>"

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
def api_patient_history(patient_id: int):
    """Get chronological history of a patient's visits, diagnoses, and severities."""
    try:
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


# --------------------------------------------------
# ANALYZE ENDPOINT
# --------------------------------------------------

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...)
):

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
        results["uploaded_image"] = f"/temp/{unique_name}"

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
        from scripts.scoring import get_visual_score
        # image_path is the /temp/... web path — convert to filesystem path
        fs_path = req.image_path
        if fs_path.startswith("/temp/"):
            fs_path = os.path.join(TEMP_DIR, fs_path[len("/temp/"):])
        elif fs_path.startswith("/"):
            fs_path = os.path.join(ROOT_DIR, fs_path.lstrip("/"))
        
        metrics = get_visual_score(fs_path, req.disease_name)
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
        # Resolve predicted_disease_name to ID
        p_id = req.predicted_disease_id
        if p_id == 0 and req.predicted_disease_name:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM diseases WHERE lower(name) = lower(%s)", (req.predicted_disease_name,))
                    res = cur.fetchone()
                    if res: p_id = res[0]
                    else: p_id = 1
                    
        # Resolve confirmed_disease_name to ID
        c_id = req.confirmed_disease_id
        if c_id == 0 and req.confirmed_disease_name:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM diseases WHERE lower(name) = lower(%s)", (req.confirmed_disease_name,))
                    res = cur.fetchone()
                    if res: c_id = res[0]
                    else: c_id = 1

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
        rx_id = save_prescription(req.case_id, req.notes, [i.model_dump() for i in req.items])
        return {"success": True, "prescription_id": rx_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/doctor_cases/{doctor_id}")
def api_get_doctor_cases(doctor_id: int):
    return get_doctor_cases(doctor_id)

@app.get("/patient_history/{patient_id}")
def api_get_patient_history(patient_id: int):
    return get_patient_history(patient_id)

@app.get("/case/{case_id}/prescription")
def api_get_prescription(case_id: int):
    rx = get_prescription(case_id)
    if rx:
        return {"success": True, "prescription": rx}
    return {"success": False, "error": "Prescription not found"}


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
