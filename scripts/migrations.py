import psycopg

DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def run_migration():
    print(f"Connecting to '{DB_NAME}' to run migrations...")
    try:
        conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                # Add is_dermatology column safely
                cur.execute("""
                    ALTER TABLE medicines 
                    ADD COLUMN IF NOT EXISTS is_dermatology BOOLEAN DEFAULT FALSE;
                """)
                print("Added 'is_dermatology' column to 'medicines'.")

                # Add created_at column safely
                cur.execute("""
                    ALTER TABLE medicines 
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                """)
                print("Added 'created_at' column to 'medicines'.")

                # Add password_hash column to doctors for auth system
                cur.execute("""
                    ALTER TABLE doctors
                    ADD COLUMN IF NOT EXISTS password_hash TEXT;
                """)
                print("Added 'password_hash' column to 'doctors'.")

                # Add created_at to doctors
                cur.execute("""
                    ALTER TABLE doctors
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                """)
                print("Added 'created_at' column to 'doctors'.")

                # Admin workflow columns
                cur.execute("""
                    ALTER TABLE doctors
                    ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
                """)
                print("Added 'is_admin' column to 'doctors'.")

                cur.execute("""
                    ALTER TABLE doctors
                    ADD COLUMN IF NOT EXISTS approved BOOLEAN DEFAULT FALSE;
                """)
                print("Added 'approved' column to 'doctors'.")

            conn.commit()
            print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error running migration: {e}")

if __name__ == "__main__":
    run_migration()
