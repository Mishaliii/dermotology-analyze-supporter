from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

import shutil
import os
import sys
import uuid

# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

sys.path.append(SCRIPTS_DIR)

try:
    from scripts.pipeline import analyze_skin_image
except ImportError:
    from pipeline import analyze_skin_image


# --------------------------------------------------
# FASTAPI INIT
# --------------------------------------------------

app = FastAPI(
    title="Clinical Dermatology Decision Support",
    description="AI-powered dermatology similarity analysis",
    version="1.0"
)

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


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

import time

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
    file: UploadFile = File(...),
    knn_k: int = Form(15), 
    search_k: int = Form(50)
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

        print(f"[INFO] Analyzing image: {temp_path} | k={knn_k}, search={search_k}")

        # ---------- RUN AI PIPELINE ----------
        results = analyze_skin_image(temp_path, knn_k=knn_k, search_k=search_k)

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
# OPTIONAL CLEANUP ENDPOINT
# --------------------------------------------------

@app.get("/cleanup-temp")
def cleanup_temp():
    removed = 0

    for f in os.listdir(TEMP_DIR):
        try:
            os.remove(os.path.join(TEMP_DIR, f))
            removed += 1
        except:
            pass

    return {"removed_files": removed}


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
