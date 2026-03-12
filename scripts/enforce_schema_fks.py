import psycopg
import sys

DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def enforce_fks_and_diseases():
    print(f"Connecting to '{DB_NAME}' to enforce FKs and restore disease columns...")
    try:
        conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                # 1. Restore predicted vs confirmed disease IDs
                print("Checking for cases.disease_id...")
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='cases' AND column_name='disease_id';")
                if cur.fetchone():
                    print("Splitting disease_id into predicted_disease_id and confirmed_disease_id...")
                    cur.execute("ALTER TABLE cases ADD COLUMN predicted_disease_id INTEGER REFERENCES diseases(id);")
                    cur.execute("ALTER TABLE cases ADD COLUMN confirmed_disease_id INTEGER REFERENCES diseases(id);")
                    
                    # Migrate data
                    cur.execute("UPDATE cases SET confirmed_disease_id = disease_id, predicted_disease_id = disease_id;")
                    
                    print("Dropping legacy disease_id...")
                    cur.execute("ALTER TABLE cases DROP COLUMN disease_id CASCADE;")
                
                # Check if old text columns still exist and drop them if so
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='cases' AND column_name='confirmed_disease';")
                if cur.fetchone():
                    cur.execute("ALTER TABLE cases DROP COLUMN confirmed_disease CASCADE;")
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='cases' AND column_name='predicted_disease';")
                if cur.fetchone():
                    cur.execute("ALTER TABLE cases DROP COLUMN predicted_disease CASCADE;")

                # 2. Enforce missing explicit foreign keys
                fks = [
                    ("cases", "cases_doctor_id_fkey", "doctor_id", "doctors", "id"),
                    ("cases", "cases_patient_id_fkey", "patient_id", "patients", "id"),
                    ("prescriptions", "prescriptions_case_id_fkey", "case_id", "cases", "id"),
                    ("prescription_items", "prescription_items_prescription_id_fkey", "prescription_id", "prescriptions", "id"),
                    ("prescription_items", "prescription_items_medicine_id_fkey", "medicine_id", "medicines", "id")
                ]

                print("Enforcing strict explicit foreign key constraints...")
                for table, constraint, col, ref_table, ref_col in fks:
                    # Check if constraint exists
                    cur.execute("""
                        SELECT constraint_name 
                        FROM information_schema.table_constraints 
                        WHERE table_name = %s AND constraint_name = %s;
                    """, (table, constraint))
                    
                    if not cur.fetchone():
                        try:
                            # It might exist with a different auto-generated name, drop if exists, but for safety just try to add
                            cur.execute(f"""
                                ALTER TABLE {table} 
                                ADD CONSTRAINT {constraint} 
                                FOREIGN KEY ({col}) REFERENCES {ref_table}({ref_col}) ON DELETE CASCADE;
                            """)
                            print(f"Added FK: {table}.{col} -> {ref_table}.{ref_col}")
                        except Exception as inner_e:
                            print(f"Skipping FK {constraint}, likely already exists under different name or data conflict.")
                            conn.rollback() # Rollback the failed constraint addition
                            conn.autocommit = True
                            conn.autocommit = False # Resetting transaction
                    else:
                        print(f"FK {constraint} already exists.")
                
            conn.commit()
            print("Successfully enforced DB schema relations!")
            
    except Exception as e:
        print(f"Error enforcing relations: {e}")
        sys.exit(1)

if __name__ == "__main__":
    enforce_fks_and_diseases()
