import psycopg
import json
import re

# DB Config
DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def get_db_connection():
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    return psycopg.connect(conn_str)

def search_patients(doctor_id: int, query: str = ""):
    """
    Returns patients linked to this doctor matching the search query.
    If query is empty, returns the most recent 20 patients for this doctor.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if query.strip():
                cur.execute("""
                    SELECT p.id, p.name, p.age, p.gender, p.medical_history
                    FROM patients p
                    JOIN doctor_patients dp ON dp.patient_id = p.id
                    WHERE dp.doctor_id = %s
                      AND p.name ILIKE %s
                    ORDER BY p.name
                    LIMIT 20
                """, (doctor_id, f"%{query.strip()}%"))
            else:
                cur.execute("""
                    SELECT p.id, p.name, p.age, p.gender, p.medical_history
                    FROM patients p
                    JOIN doctor_patients dp ON dp.patient_id = p.id
                    WHERE dp.doctor_id = %s
                    ORDER BY p.id DESC
                    LIMIT 20
                """, (doctor_id,))

            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "age": r[2],
                    "gender": r[3] or "",
                    "medical_history": r[4] or ""
                }
                for r in rows
            ]


def create_patient(doctor_id: int, name: str, age: int, gender: str = "", medical_history: str = ""):
    """
    Creates a new patient and links them to the doctor.
    Returns {success, patient_id, name, age, gender, medical_history}.
    """
    name = name.strip()
    if not name:
        return {"success": False, "error": "Patient name is required."}
    if age is None or age < 0 or age > 150:
        return {"success": False, "error": "Please provide a valid age."}

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO patients (name, age, gender, medical_history)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (name, age, gender.strip(), medical_history.strip()))
                patient_id = cur.fetchone()[0]

                # Link patient to this doctor
                cur.execute("""
                    INSERT INTO doctor_patients (doctor_id, patient_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (doctor_id, patient_id))

            conn.commit()

        return {
            "success": True,
            "patient_id": patient_id,
            "name": name,
            "age": age,
            "gender": gender,
            "medical_history": medical_history
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# Mapping of keywords to canonical disease names stored in DB.
# Order matters — more specific terms first.
_DISEASE_KEYWORD_MAP = [
    ("acne",       "Acne"),
    ("psoriasis",  "Psoriasis"),
    ("eczema",     "Eczema"),
    ("dermatitis", "Eczema"),
    ("vitiligo",   "Vitiligo"),
    ("alopecia",   "Alopecia"),
]

def _resolve_disease_id(cur, disease_name: str):
    """
    Try to resolve a (possibly AI-generated) disease name like
    'Acne_Vulgaris' or 'Guttate Psoriasis' to the canonical disease ID used
    in disease_treatments.  Returns (disease_id, canonical_name) or (None, None).
    
    Strategy:
      1. Exact match (fastest)
      2. Keyword alias lookup - check if the name contains a known keyword
         and look up the canonical name in disease_treatments 
    """
    clean = disease_name.replace('_', ' ').strip()

    # 1. Exact match (case-insensitive)
    cur.execute("SELECT id FROM diseases WHERE lower(name) = lower(%s)", (clean,))
    row = cur.fetchone()
    if row:
        return row[0], clean

    # 2. Keyword-based alias lookup
    lower_clean = clean.lower()
    for keyword, canonical in _DISEASE_KEYWORD_MAP:
        if keyword in lower_clean:
            cur.execute("SELECT id FROM diseases WHERE lower(name) = lower(%s)", (canonical,))
            row = cur.fetchone()
            if row:
                return row[0], canonical

    return None, None

def create_case(doctor_id: int, patient_id: int, image_path: str, predicted_disease_id: int, confirmed_disease_id: int, 
                severity_json: dict, ai_confidence: float):
    """
    Called when the doctor confirms the calculator screen and moves to the prescription screen.
    Returns the newly generated case_id.
    """
    # For MVP: if patient or doctor don't exist, we can auto-create dummy ones for testing
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Ensure dummy doctor exists if 0
            if doctor_id == 0:
                cur.execute("SELECT id FROM doctors LIMIT 1")
                doc = cur.fetchone()
                if not doc:
                    cur.execute("INSERT INTO doctors (name, email) VALUES ('Dr. Demo', 'dr@demo.com') RETURNING id")
                    doctor_id = cur.fetchone()[0]
                else:
                    doctor_id = doc[0]
            
            # 2. Ensure dummy patient exists if 0
            if patient_id == 0:
                cur.execute("SELECT id FROM patients LIMIT 1")
                pat = cur.fetchone()
                if not pat:
                    cur.execute("INSERT INTO patients (name, age) VALUES ('John Doe', 30) RETURNING id")
                    patient_id = cur.fetchone()[0]
                    # Map to the new Many-to-Many junction table
                    cur.execute("INSERT INTO doctor_patients (doctor_id, patient_id) VALUES (%s, %s)", (doctor_id, patient_id))
                else:
                    patient_id = pat[0]

            # 3. Insert Case
            cur.execute("""
                INSERT INTO cases (doctor_id, patient_id, image_path, predicted_disease_id, confirmed_disease_id, severity_json, ai_confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (doctor_id, patient_id, image_path, predicted_disease_id, confirmed_disease_id, json.dumps(severity_json), ai_confidence))
            
            case_id = cur.fetchone()[0]
            
            # Fetch the actual names from the DB to return to the UI
            cur.execute("SELECT name FROM doctors WHERE id = %s", (doctor_id,))
            doc_name = cur.fetchone()[0]
            
            cur.execute("SELECT name, age FROM patients WHERE id = %s", (patient_id,))
            pat_row = cur.fetchone()
            pat_name = pat_row[0]
            pat_age = pat_row[1]

            conn.commit()
            return {
                "case_id": case_id, 
                "doctor_name": doc_name, 
                "patient_name": pat_name, 
                "patient_age": pat_age
            }

def search_medicines(query: str, disease: str = ""):
    """
    Returns autocomplete suggestions for medicines table.
    When a disease name is provided, only medicines linked to that disease
    via disease_treatments are returned (smart disease-aware filtering).
    Uses keyword-based matching so 'Acne_Vulgaris' correctly resolves to 'Acne'.
    Falls back to a general search when no disease context exists.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:

            if disease:
                disease_id, canonical = _resolve_disease_id(cur, disease)

                if disease_id:
                    cur.execute("""
                        SELECT DISTINCT m.id, m.name, m.generic_name, m.form, m.strength
                        FROM medicines m
                        INNER JOIN disease_treatments dt ON dt.medicine_id = m.id
                        WHERE dt.disease_id = %s
                          AND (m.name ILIKE %s OR m.generic_name ILIKE %s)
                        ORDER BY m.name
                        LIMIT 10
                    """, (disease_id, f"%{query}%", f"%{query}%"))

                    results = []
                    for row in cur.fetchall():
                        results.append({
                            "id": row[0],
                            "name": row[1],
                            "generic_name": row[2] or "",
                            "form": row[3] or "",
                            "strength": row[4] or ""
                        })
                    return results

            # Fallback: no disease context — general search across all medicines
            cur.execute("""
                SELECT id, name, generic_name, form, strength
                FROM medicines
                WHERE name ILIKE %s OR generic_name ILIKE %s
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))

            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "name": row[1],
                    "generic_name": row[2] or "",
                    "form": row[3] or "",
                    "strength": row[4] or ""
                })
            return results

def add_medicine(name: str, generic_name: str, category: str, form: str, strength: str):
    """
    Adds a new custom medicine to the database from the UI.
    Returns the newly created or existing medicine ID.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if it exists
            cur.execute("""
                SELECT id FROM medicines 
                WHERE name ILIKE %s AND form ILIKE %s AND strength ILIKE %s
            """, (name, form, strength))
            existing = cur.fetchone()
            if existing:
                return {"success": True, "medicine_id": existing[0], "message": "Already exists"}

            cur.execute("""
                INSERT INTO medicines (name, generic_name, category, form, strength, is_dermatology)
                VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id
            """, (name, generic_name, category, form, strength))
            
            med_id = cur.fetchone()[0]
            conn.commit()
            return {"success": True, "medicine_id": med_id}


def generate_treatment_suggestions(disease_name: str, severity_score: int):
    """
    The CDSS AI engine. Queries disease_treatments by disease + severity.
    Uses keyword-based disease resolution so AI outputs like 'Acne_Vulgaris'
    and 'Guttate Psoriasis' both resolve to their seeded canonical disease rows.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            disease_id, canonical = _resolve_disease_id(cur, disease_name)
            if not disease_id:
                print(f"[CDSS] No disease_treatments found for: {disease_name!r} (canonical: {canonical!r})")
                return []

            # Query the Rules Engine
            cur.execute("""
                SELECT m.id, m.name, m.form, dt.line_of_therapy, m.strength
                FROM disease_treatments dt
                JOIN medicines m ON dt.medicine_id = m.id
                WHERE dt.disease_id = %s
                  AND %s >= dt.severity_min
                  AND %s <= dt.severity_max
                ORDER BY dt.severity_min ASC
            """, (disease_id, severity_score, severity_score))

            suggestions = []
            for row in cur.fetchall():
                line = row[3] or ""
                # Provide a smart default duration based on line of therapy
                if "Maintenance" in line:
                    duration = "Ongoing"
                elif "Systemic" in line or "Biologic" in line:
                    duration = "3 months"
                else:
                    duration = "4 weeks"

                suggestions.append({
                    "medicine_id": row[0],
                    "name": row[1],
                    "form": row[2],
                    "line_of_therapy": line,
                    "strength": row[4] or "",
                    "dose": "Use as directed",
                    "duration": duration
                })

            return suggestions

def save_prescription(case_id: int, notes: str, items: list):
    """
    Saves the final edits chosen by the physical doctor.
    items = [{"medicine_id": 1, "dose": "1 pill", "frequency": "Daily", "duration": "4 weeks"}]
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Save Header
            cur.execute("""
                INSERT INTO prescriptions (case_id, notes)
                VALUES (%s, %s) RETURNING id
            """, (case_id, notes))
            prescription_id = cur.fetchone()[0]
            
            # 2. Save Line Items
            for item in items:
                med_id = item.get("medicine_id")
                med_name = item.get("name", "").strip()
                
                # If the UI passed a randomly generated fake ID (custom entry)
                if med_id >= 1000 and med_name:
                    # Attempt to safely insert the custom name into the medicines dictionary
                    cur.execute("""
                        INSERT INTO medicines (name, form) 
                        VALUES (%s, 'Custom')
                        ON CONFLICT (name) DO NOTHING
                        RETURNING id
                    """, (med_name,))
                    
                    row = cur.fetchone()
                    if row:
                        med_id = row[0]
                    else:
                        # If conflict existed, just retrieve the existing ID
                        cur.execute("SELECT id FROM medicines WHERE name = %s", (med_name,))
                        med_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO prescription_items (prescription_id, medicine_id, dosage, frequency, duration, instructions)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    prescription_id, 
                    med_id, 
                    item.get("dose", ""), 
                    item.get("frequency", ""), 
                    item.get("duration", ""), 
                    item.get("instructions", "")
                ))
            
            
            conn.commit()
            return prescription_id

def get_doctor_cases(doctor_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, p.name, ds.name as predicted_disease_name, c.created_at
                FROM cases c 
                JOIN patients p ON c.patient_id = p.id
                JOIN diseases ds ON c.predicted_disease_id = ds.id
                WHERE c.doctor_id = %s
                ORDER BY c.created_at DESC
                LIMIT 50
            """, (doctor_id,))
            
            cases = [{"id": r[0], "patient_name": r[1], "disease": r[2], "date": str(r[3])} for r in cur.fetchall()]
            return cases

def get_patient_history(patient_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, ds.name as confirmed_disease_name, c.severity_json, c.created_at, pr.id
                FROM cases c
                JOIN diseases ds ON c.confirmed_disease_id = ds.id
                LEFT JOIN prescriptions pr ON c.id = pr.case_id
                WHERE c.patient_id = %s
                ORDER BY c.created_at ASC
            """, (patient_id,))
            
            history = [{"case_id": r[0], "disease": r[1], "severity": r[2], "date": str(r[3]), "has_prescription": bool(r[4])} for r in cur.fetchall()]
            return history

def get_prescription(case_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pr.id, pr.notes, pr.created_at, d.name, ds.name as confirmed_disease_name, p.name, p.age
                FROM prescriptions pr
                JOIN cases c ON pr.case_id = c.id
                JOIN diseases ds ON c.confirmed_disease_id = ds.id
                JOIN doctors d ON c.doctor_id = d.id
                JOIN patients p ON c.patient_id = p.id
                WHERE pr.case_id = %s
            """, (case_id,))
            rx = cur.fetchone()
            if not rx: return None
            
            prescription = {
                "prescription_id": rx[0], "notes": rx[1], "date": str(rx[2]),
                "doctor_name": rx[3], "diagnosis": rx[4], "patient_name": rx[5], "patient_age": rx[6],
                "items": []
            }
            
            # Items
            cur.execute("""
                SELECT m.name, pi.dosage, pi.frequency, pi.duration, pi.instructions
                FROM prescription_items pi
                JOIN medicines m ON pi.medicine_id = m.id
                WHERE pi.prescription_id = %s
            """, (rx[0],))
            
            for row in cur.fetchall():
                prescription["items"].append({
                    "medicine": row[0], "dosage": row[1], "frequency": row[2], 
                    "duration": row[3], "instructions": row[4]
                })
                
            return prescription
