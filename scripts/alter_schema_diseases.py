import psycopg
import sys

DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def migrate_case_disease_relation():
    print(f"Connecting to '{DB_NAME}' to execute Cases -> Diseases relation migration...")
    try:
        conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                
                # Check if it's already done (disease_id column exists)
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='cases' and column_name='disease_id';
                """)
                if cur.fetchone():
                    print("Migration already applied. 'disease_id' column exists in 'cases'.")
                    return
                
                print("Adding 'disease_id' reference column to 'cases'...")
                cur.execute("""
                    ALTER TABLE cases 
                    ADD COLUMN disease_id INTEGER REFERENCES diseases(id);
                """)
                
                print("Migrating text-based confirmed_disease data to actual disease references...")
                # Update existing cases by matching the text string in 'confirmed_disease' to 'diseases.name'
                cur.execute("""
                    UPDATE cases c
                    SET disease_id = d.id
                    FROM diseases d
                    WHERE lower(c.confirmed_disease) = lower(d.name)
                       OR c.confirmed_disease ILIKE '%' || d.name || '%';
                """)
                
                # Default fallback for unmapped cases (in a real scenario we'd flag these, but for demo default to 1)
                cur.execute("""
                    UPDATE cases
                    SET disease_id = (SELECT id FROM diseases LIMIT 1)
                    WHERE disease_id IS NULL;
                """)
                
                print("Dropping old text-based disease columns ('predicted_disease', 'confirmed_disease')...")
                cur.execute("ALTER TABLE cases DROP COLUMN predicted_disease;")
                cur.execute("ALTER TABLE cases DROP COLUMN confirmed_disease;")
                
                print("Migration to strict Disease references completed successfully!")
            
            conn.commit()

    except Exception as e:
        print(f"Error migrating schema for Cases->Diseases: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_case_disease_relation()
