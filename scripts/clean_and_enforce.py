import psycopg
import sys

DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def clean_orphans_and_enforce():
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            # 1. DELETE ORPHANS
            print("Deleting orphaned prescription_items (medicine_id)...")
            cur.execute("""
                DELETE FROM prescription_items 
                WHERE medicine_id NOT IN (SELECT id FROM medicines);
            """)
            
            print("Deleting orphaned prescription_items (prescription_id)...")
            cur.execute("""
                DELETE FROM prescription_items 
                WHERE prescription_id NOT IN (SELECT id FROM prescriptions);
            """)
            
            print("Deleting orphaned prescriptions (case_id)...")
            cur.execute("""
                DELETE FROM prescriptions 
                WHERE case_id NOT IN (SELECT id FROM cases);
            """)
            conn.commit()
            print("Orphans deleted. Now trying to add FKs...")

            # 2. ENFORCE FKs
            fks = [
                ("cases", "cases_doctor_id_fkey_2", "doctor_id", "doctors", "id"),
                ("cases", "cases_patient_id_fkey_2", "patient_id", "patients", "id"),
                ("prescriptions", "prescriptions_case_id_fkey_2", "case_id", "cases", "id"),
                ("prescription_items", "prescription_items_prescription_id_fkey_2", "prescription_id", "prescriptions", "id"),
                ("prescription_items", "prescription_items_medicine_id_fkey_2", "medicine_id", "medicines", "id")
            ]

            for table, constraint, col, ref_table, ref_col in fks:
                # First, drop if exists, then add
                try: 
                    cur.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint};")
                except:
                    conn.rollback()
                    conn.autocommit = True
                    conn.autocommit = False

                try:
                    cur.execute(f"""
                        ALTER TABLE {table} 
                        ADD CONSTRAINT {constraint} 
                        FOREIGN KEY ({col}) REFERENCES {ref_table}({ref_col}) ON DELETE CASCADE;
                    """)
                    print(f"Successfully added FK: {table}.{col} -> {ref_table}.{ref_col}")
                except Exception as e:
                    print(f"FAILED to add FK {constraint}: {e}")
                    conn.rollback()
                    conn.autocommit = True
                    conn.autocommit = False
            
        conn.commit()
        print("Done!")

if __name__ == "__main__":
    clean_orphans_and_enforce()
