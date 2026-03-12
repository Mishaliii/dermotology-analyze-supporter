import psycopg
import sys
import os

DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def migrate_doctor_patient_relations():
    print(f"Connecting to '{DB_NAME}' to execute Many-to-Many Doctor-Patient migration...")
    try:
        conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                
                # Check if doctor_patients already exists
                cur.execute("SELECT to_regclass('public.doctor_patients');")
                exists = cur.fetchone()[0]
                
                if exists:
                    print("Table 'doctor_patients' already exists. Skipping creation.")
                else:
                    print("Creating 'doctor_patients' junction table...")
                    cur.execute("""
                        CREATE TABLE doctor_patients (
                            doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
                            patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
                            primary_doctor BOOLEAN DEFAULT TRUE,
                            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (doctor_id, patient_id)
                        );
                    """)
                    
                    # Migration: Copy existing relationships from patients table
                    # Check if doctor_id column exists in patients
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='patients' and column_name='doctor_id';
                    """)
                    col_exists = cur.fetchone()
                    
                    if col_exists:
                        print("Migrating existing foreign keys from 'patients' table to 'doctor_patients'...")
                        cur.execute("""
                            INSERT INTO doctor_patients (doctor_id, patient_id)
                            SELECT doctor_id, id FROM patients WHERE doctor_id IS NOT NULL
                            ON CONFLICT DO NOTHING;
                        """)
                        
                        print("Dropping 'doctor_id' column from 'patients' table...")
                        cur.execute("ALTER TABLE patients DROP COLUMN doctor_id;")
                    
                    print("Migration completed successfully!")

            conn.commit()
            
    except Exception as e:
        print(f"Error migrating schema: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_doctor_patient_relations()
