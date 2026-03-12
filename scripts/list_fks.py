import psycopg

DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def write_fks_to_file():
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    tc.table_name, 
                    kcu.column_name, 
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY';
            """)
            fks = cur.fetchall()
            
            with open("temp_fks_utf8.txt", "w", encoding="utf-8") as f:
                f.write("--- POSTGRES FOREIGN KEYS ---\n")
                for fk in fks:
                    f.write(f"{fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}\n")
            
            print(f"Wrote {len(fks)} FKs to temp_fks_utf8.txt")

if __name__ == "__main__":
    write_fks_to_file()
