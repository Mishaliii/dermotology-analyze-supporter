import psycopg
import sys

# Database Credentials
DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def seed_users():
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                # Insert Demo Doctor (id will likely be 1 if it's the first insert, but we'll use RETURNING id just in case)
                cur.execute("""
                    INSERT INTO doctors (name, email, license_number, clinic_name)
                    VALUES ('Dr. Demo', 'demo@clinic.com', 'LIC12345', 'Derm Support Clinic')
                    ON CONFLICT (email) DO NOTHING
                    RETURNING id;
                """)
                doctor_result = cur.fetchone()
                if doctor_result:
                    doc_id = doctor_result[0]
                    print(f"Created Demo Doctor with ID: {doc_id}")
                else:
                    cur.execute("SELECT id FROM doctors WHERE email = 'demo@clinic.com'")
                    doc_id = cur.fetchone()[0]
                    print(f"Demo Doctor already exists with ID: {doc_id}")

                # Insert Demo Patient
                cur.execute("""
                    INSERT INTO patients (name, age, gender, medical_history)
                    VALUES ('John Doe', 30, 'Male', 'No known allergies. Previous history of mild eczema.')
                    RETURNING id;
                """)
                pat_id = cur.fetchone()[0]
                print(f"Created Demo Patient with ID: {pat_id}")
                
                # Link Patient to Doctor
                cur.execute("""
                    INSERT INTO doctor_patients (doctor_id, patient_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                """, (doc_id, pat_id))
            conn.commit()
            print("Successfully seeded demo doctor and patient.")
    except Exception as e:
        print(f"Error seeding demo users: {e}")

if __name__ == "__main__":
    seed_users()
