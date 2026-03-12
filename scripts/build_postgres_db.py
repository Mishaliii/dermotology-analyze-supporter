import os
import json
import psycopg
import sys
import numpy as np

# Constants
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ISD-198")
CLASSES_JSON_PATH = os.path.join(DATA_DIR, "metadata", "classes.json")
EMBEDDING_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "embeddings")
IMAGE_PATHS_NPY = os.path.join(EMBEDDING_DIR, "image_paths.npy")

# Database Credentials
DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def build_database():
    print(f"Connecting to database '{DB_NAME}' for data migration...")
    
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                
                # 1. Clear existing generic data if re-running
                cur.execute("TRUNCATE TABLE disease_treatments CASCADE;")
                cur.execute("TRUNCATE TABLE medicines CASCADE;")
                cur.execute("TRUNCATE TABLE images CASCADE;")
                cur.execute("TRUNCATE TABLE diseases CASCADE;")

                print("\n1. Migrating Diseases from classes.json")
                if not os.path.exists(CLASSES_JSON_PATH):
                    print("ERROR: classes.json not found! Cannot map diseases.")
                    return False
                    
                with open(CLASSES_JSON_PATH, "r") as f:
                    classes = json.load(f)
                
                # Reverse mapping to get index from name (optional, but good for validation)
                disease_name_to_db_id = {}
                
                for idx, disease_name in classes.items():
                    # Determine calculator type based on basic keywords. Can be updated later.
                    calc_type = 'None'
                    if 'Psoriasis' in disease_name: calc_type = 'PASI'
                    elif 'Acne' in disease_name: calc_type = 'GAGS'
                    elif 'Eczema' in disease_name or 'Dermatitis' in disease_name: calc_type = 'EASI'
                    elif 'Vitiligo' in disease_name: calc_type = 'VASI'
                    elif 'Melanoma' in disease_name: calc_type = 'ABCDE'
                    elif 'Alopecia' in disease_name: calc_type = 'SALT'
                    
                    cur.execute("""
                        INSERT INTO diseases (name, calculator_type)
                        VALUES (%s, %s) RETURNING id
                    """, (disease_name, calc_type))
                    
                    db_id = cur.fetchone()[0]
                    disease_name_to_db_id[disease_name] = db_id
                    
                print(f"-> Inserted {len(classes)} diseases.")

                # 2. Map Images and FAISS IDs
                print("\n2. Migrating Images & Mapping FAISS IDs")
                if not os.path.exists(IMAGE_PATHS_NPY):
                    print("ERROR: image_paths.npy not found!")
                    return False
                    
                image_paths = np.load(IMAGE_PATHS_NPY, allow_pickle=True)
                    
                faiss_inserted = 0
                for faiss_id, image_path in enumerate(image_paths):
                    # image_path might be absolute or relative, extract disease name appropriately
                    # It's usually "Disease/image.jpg"
                    disease_name = os.path.basename(os.path.dirname(image_path))
                    
                    if disease_name in disease_name_to_db_id:
                        db_disease_id = disease_name_to_db_id[disease_name]

                        cur.execute("""
                            INSERT INTO images (faiss_id, disease_id, relative_path)
                            VALUES (%s, %s, %s)
                        """, (faiss_id, db_disease_id, image_path))

                        faiss_inserted += 1
                        
                print(f"-> Inserted {faiss_inserted} images perfectly mapped to FAISS.")

                # 3. Inject Starter Medicines (Demo Base)
                print("\n3. Injecting CDSS Pharmacology Rules")
                starter_medicines = [
                    ('Adapalene 0.1%', 'Adapalene', 'Retinoid', 'Gel', '0.1%'),
                    ('Benzoyl Peroxide 5%', 'Benzoyl Peroxide', 'Antibacterial', 'Wash', '5%'),
                    ('Oral Isotretinoin', 'Isotretinoin', 'Systemic Retinoid', 'Capsule', '20mg'),
                    ('Topical Corticosteroid (Mild)', 'Hydrocortisone', 'Steroid', 'Cream', '1%'),
                    ('Topical Corticosteroid (Strong)', 'Clobetasol', 'Steroid', 'Ointment', '0.05%'),
                    ('Methotrexate', 'Methotrexate', 'Immunosuppressant', 'Tablet', '2.5mg'),
                    ('Tacrolimus 0.1%', 'Tacrolimus', 'Calcineurin Inhibitor', 'Ointment', '0.1%'),
                    ('Minoxidil 5%', 'Minoxidil', 'Vasodilator', 'Solution', '5%')
                ]
                
                medicine_name_to_id = {}
                for m in starter_medicines:
                    cur.execute("""
                        INSERT INTO medicines (name, generic_name, category, form, strength)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id
                    """, m)
                    medicine_name_to_id[m[0]] = cur.fetchone()[0]

                # 4. Inject Starter Treatment Rules
                # Disease name -> (Medicine Name, Severity Min, Severity Max, Line of Therapy)
                rules = [
                    ('Acne and Rosacea', 'Adapalene 0.1%', 1, 2, 'Topical - 1st Line'),
                    ('Acne and Rosacea', 'Benzoyl Peroxide 5%', 1, 3, 'Topical - Wash'),
                    ('Acne and Rosacea', 'Oral Isotretinoin', 3, 4, 'Systemic - Severe/Nodulocystic'),
                    ('Psoriasis pictures Lichen Planus and related diseases', 'Topical Corticosteroid (Strong)', 1, 2, 'Topical - Mild/Moderate'),
                    ('Psoriasis pictures Lichen Planus and related diseases', 'Methotrexate', 3, 4, 'Systemic - Severe (PASI > 10)'),
                    ('Eczema Photos', 'Topical Corticosteroid (Mild)', 1, 2, 'Topical - Flare up'),
                    ('Eczema Photos', 'Tacrolimus 0.1%', 1, 4, 'Maintenance / Face'),
                    ('Hair Loss Photos Alopecia and other Hair Diseases', 'Minoxidil 5%', 1, 3, 'Topical - Daily Maintenance')
                ]
                
                rules_inserted = 0
                for rule_disease, rule_med, s_min, s_max, line in rules:
                    if rule_disease in disease_name_to_db_id and rule_med in medicine_name_to_id:
                        d_id = disease_name_to_db_id[rule_disease]
                        m_id = medicine_name_to_id[rule_med]
                        
                        cur.execute("""
                            INSERT INTO disease_treatments (disease_id, medicine_id, severity_min, severity_max, line_of_therapy)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (d_id, m_id, s_min, s_max, line))
                        rules_inserted += 1
                        
                print(f"-> Injected {len(starter_medicines)} Medicines and {rules_inserted} Rule Logic paths.")
                
            conn.commit()
            print("\n---------------------------------------------------------")
            print("OK - Migration Complete! PostgreSQL is now the Source of Truth.")
            print("You may safely delete classes.json.")
            
            return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False

if __name__ == "__main__":
    build_database()
