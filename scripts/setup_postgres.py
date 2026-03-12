import psycopg
import sys

# User's provided credentials
DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def create_database():
    print(f"Connecting to PostgreSQL on {DB_HOST}:{DB_PORT} to check database '{DB_NAME}'...")
    try:
        # Connect to the default 'postgres' database first to create the new one
        conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname=postgres"
        with psycopg.connect(conn_str, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Check if database exists
                cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_NAME,))
                exists = cur.fetchone()
                
                if not exists:
                    print(f"Creating database '{DB_NAME}'...")
                    cur.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(DB_NAME)))
                else:
                    print(f"Database '{DB_NAME}' already exists.")
                    
        return True
    except Exception as e:
        print(f"Error connecting to PostgreSQL or creating database: {e}")
        return False

def create_tables():
    print(f"\nConnecting to '{DB_NAME}' to establish schema...")
    try:
        conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                # 1. DOCTORS (Multi-Tenancy Core)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS doctors (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        license_number TEXT,
                        clinic_name TEXT
                    );
                """)

                # 2. DISEASES (Knowledge Base Reference)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS diseases (
                        id SERIAL PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        calculator_type TEXT,
                        base_guidelines TEXT
                    );
                """)

                # 3. IMAGES (Replaces Folder Scanning, maps FAISS index)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS images (
                        id SERIAL PRIMARY KEY,
                        faiss_id INTEGER UNIQUE,
                        disease_id INTEGER REFERENCES diseases(id),
                        relative_path TEXT NOT NULL
                    );
                """)

                # 4. PATIENTS (Clinical Entity)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS patients (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        age INTEGER,
                        gender TEXT,
                        medical_history TEXT
                    );
                """)

                # 4b. DOCTOR_PATIENTS (M:N Relation)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS doctor_patients (
                        doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
                        patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
                        primary_doctor BOOLEAN DEFAULT TRUE,
                        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (doctor_id, patient_id)
                    );
                """)

                # 5. CASES (The Core Consultation Object)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cases (
                        id SERIAL PRIMARY KEY,
                        doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
                        patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
                        image_path TEXT,
                        predicted_disease TEXT,
                        confirmed_disease TEXT,
                        severity_json TEXT,
                        ai_confidence REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 6. MEDICINES (Drug Dictionary)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS medicines (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        generic_name TEXT,
                        category TEXT,
                        form TEXT,
                        strength TEXT,
                        is_dermatology BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 7. DISEASE TREATMENTS (The Smart Rule Engine)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS disease_treatments (
                        id SERIAL PRIMARY KEY,
                        disease_id INTEGER REFERENCES diseases(id) ON DELETE CASCADE,
                        medicine_id INTEGER REFERENCES medicines(id),
                        severity_min INTEGER,
                        severity_max INTEGER,
                        line_of_therapy TEXT
                    );
                """)

                # 8a. PRESCRIPTIONS (Header)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS prescriptions (
                        id SERIAL PRIMARY KEY,
                        case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 8b. PRESCRIPTION ITEMS (Line Items)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS prescription_items (
                        id SERIAL PRIMARY KEY,
                        prescription_id INTEGER REFERENCES prescriptions(id) ON DELETE CASCADE,
                        medicine_id INTEGER REFERENCES medicines(id),
                        dosage TEXT,
                        frequency TEXT,
                        duration TEXT,
                        instructions TEXT,
                        UNIQUE (prescription_id, medicine_id)
                    );
                """)

            conn.commit()
            print("OK - All 8 CDSS tables created successfully!")
        
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    print("--- Clinical Decision Support System: Database Setup ---")
    if create_database():
        create_tables()
    else:
        sys.exit(1)
