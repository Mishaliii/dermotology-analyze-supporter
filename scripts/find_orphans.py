import psycopg

DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def check_orphans():
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            # Check prescriptions -> cases
            cur.execute("""
                SELECT id, case_id FROM prescriptions 
                WHERE case_id NOT IN (SELECT id FROM cases);
            """)
            orphans_1 = cur.fetchall()
            print("Orphan prescriptions (invalid case_id):", orphans_1)
            
            # Check prescription_items -> prescriptions
            cur.execute("""
                SELECT id, prescription_id FROM prescription_items 
                WHERE prescription_id NOT IN (SELECT id FROM prescriptions);
            """)
            orphans_2 = cur.fetchall()
            print("Orphan prescription_items (invalid prescription_id):", orphans_2)
            
            # Check prescription_items -> medicines
            cur.execute("""
                SELECT id, medicine_id FROM prescription_items 
                WHERE medicine_id NOT IN (SELECT id FROM medicines);
            """)
            orphans_3 = cur.fetchall()
            print("Orphan prescription_items (invalid medicine_id):", orphans_3)

if __name__ == "__main__":
    check_orphans()
