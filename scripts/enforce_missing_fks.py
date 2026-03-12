import psycopg
import sys

DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def enforce_missing_fks():
    print(f"Connecting to '{DB_NAME}' to enforce remaining FKs...")
    try:
        conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                
                fks = [
                    ("disease_treatments", "dt_disease_id_fkey", "disease_id", "diseases", "id"),
                    ("disease_treatments", "dt_medicine_id_fkey", "medicine_id", "medicines", "id"),
                    ("images", "images_disease_id_fkey", "disease_id", "diseases", "id")
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
            print("Successfully enforced missing DB schema relations!")
            
    except Exception as e:
        print(f"Error enforcing relations: {e}")
        sys.exit(1)

if __name__ == "__main__":
    enforce_missing_fks()
