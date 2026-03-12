import pandas as pd
import psycopg
import re
import sys
import os

# DB Config
DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13" 
DB_NAME = "clinical_data"

def get_db_connection():
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    return psycopg.connect(conn_str)

def clean_and_import(excel_path):
    print(f"Reading {excel_path}...")
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"Error reading excel file: {e}")
        return

    # Assuming the Excel has columns like 'Medicine name', 'Form', 'Strength'. We will try to adapt flexibly.
    # But since the user requested Rule 2 with "Hydrocortisone 1% cream", we assume there's a main column we need to parse if it's combined,
    # or separate columns. We'll handle a combined 'name' field if present, or use provided fields.
    
    # Let's map any possible column names to our standard ones
    col_map = {}
    for col in df.columns:
        c = col.lower().strip()
        if 'name' in c or 'medicine' in c:
            col_map[col] = 'raw_name'
        elif 'form' in c:
            col_map[col] = 'form'
        elif 'strength' in c:
            col_map[col] = 'strength'
        elif 'category' in c or 'class' in c:
            col_map[col] = 'category'
            
    df = df.rename(columns=col_map)
    if 'raw_name' not in df.columns:
        print("Could not find a 'name' column in the Excel file.")
        if len(df.columns) > 0:
            df = df.rename(columns={df.columns[0]: 'raw_name'}) # Fallback to first column
    
    # Ensure columns exist
    for col in ['category', 'form', 'strength']:
        if col not in df.columns:
            df[col] = ""
            
    # Rule 4: Auto Category Mapping
    category_map = {
        'hydrocortisone': 'corticosteroid',
        'adapalene': 'retinoid',
        'doxycycline': 'antibiotic',
        'ketoconazole': 'antifungal',
        'betamethasone': 'corticosteroid',
        'mometasone': 'corticosteroid',
        'clobetasol': 'corticosteroid',
        'isotretinoin': 'retinoid',
        'tretinoin': 'retinoid',
        'clindamycin': 'antibiotic',
        'erythromycin': 'antibiotic',
        'terbinafine': 'antifungal',
        'itraconazole': 'antifungal',
        'methotrexate': 'immunomodulator',
        'cyclosporine': 'immunomodulator',
        'cetirizine': 'antihistamine',
        'loratadine': 'antihistamine',
        'salicylic acid': 'keratolytic',
        'urea': 'keratolytic',
        'white soft paraffin': 'emollient',
        'liquid paraffin': 'emollient',
        'adalimumab': 'biologic',
        'secukinumab': 'biologic'
    }

    processed_medicines = {} # For deduplication
    
    for idx, row in df.iterrows():
        raw_name = str(row['raw_name']) if pd.notna(row['raw_name']) else ""
        form_val = str(row['form']) if pd.notna(row['form']) else ""
        strength_val = str(row['strength']) if pd.notna(row['strength']) else ""
        category_val = str(row['category']) if pd.notna(row['category']) else ""
        
        # Rule 2: Name Normalization
        # e.g., "Hydrocortisone 1% cream"
        name = raw_name
        form = form_val
        strength = strength_val
        
        if not form_val and not strength_val:
            # Try to extract from name
            # Look for strength (e.g., 1%, 500mg, 0.1% w/w)
            strength_match = re.search(r'(\d+(?:\.\d+)?\s*(?:mg|g|mcg|%|IU|w/w|w/v)(?:/[ml|g|Tablet]+)?)', raw_name, re.IGNORECASE)
            if strength_match:
                strength = strength_match.group(1)
                name = raw_name.replace(strength_match.group(0), "").strip()
            
            # Simple form extraction
            forms_list = ['cream', 'ointment', 'gel', 'lotion', 'tablet', 'capsule', 'syrup', 'injection', 'solution', 'shampoo']
            for f in forms_list:
                if f in name.lower():
                    form = f
                    name = re.sub(rf'\b{f}\b', '', name, flags=re.IGNORECASE).strip()
                    break
                    
        # Clean up punctuation and whitespace
        name = re.sub(r'[\s,]+$', '', name).strip()
        name = re.sub(r'^[,\s]+', '', name).strip()
        generic_name = name.lower()

        # Rule 4 Implementation: Auto map if category is empty
        if not category_val:
            for keyword, cat in category_map.items():
                if keyword in generic_name:
                    category_val = cat
                    break
                    
        # Rule 1: Dermatology Filter
        dermatology_keywords = ['corticosteroid', 'antibiotic', 'antifungal', 'retinoid', 
                                'immunomodulator', 'antihistamine', 'keratolytic', 'emollient', 'biologic']
        
        is_dermatology = False
        cat_lower = category_val.lower()
        if any(keyword in cat_lower for keyword in dermatology_keywords):
            is_dermatology = True
            
        # If it didn't hit a category keyword, let's also check the name itself
        if not is_dermatology:
             for keyword in dermatology_keywords:
                 if keyword in category_map.values(): # Just checking if the name matches a known mapping
                     for k, v in category_map.items():
                         if k in generic_name and v in dermatology_keywords:
                             is_dermatology = True
                             category_val = v
                             break
                             
        # Capitalize nicely
        name_capitalized = name.title() if name else "Unknown"
        
        # Rule 3: Remove Duplicates (generic_name + strength + form)
        dedup_key = f"{generic_name}_{strength}_{form}".lower()
        
        if dedup_key not in processed_medicines and name_capitalized != "Unknown":
            processed_medicines[dedup_key] = {
                'name': name_capitalized,
                'generic_name': name_capitalized,
                'category': category_val,
                'form': form,
                'strength': strength,
                'is_dermatology': is_dermatology
            }

    print(f"Processed {len(processed_medicines)} unique medicines.")
    if len(processed_medicines) == 0:
        return

    # Insert into database
    print("Importing to PostgreSQL...")
    count = 0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for key, med in processed_medicines.items():
                cur.execute("""
                    INSERT INTO medicines (name, generic_name, category, form, strength, is_dermatology)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    med['name'], 
                    med['generic_name'], 
                    med['category'], 
                    med['form'], 
                    med['strength'], 
                    med['is_dermatology']
                ))
                count += 1
        conn.commit()
    print(f"Successfully inserted {count} medicines.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        # Default fallback
        excel_path = os.path.join(os.path.dirname(__file__), "..", "data", "who_eml.xlsx")

    if os.path.exists(excel_path):
        clean_and_import(excel_path)
    else:
        print(f"File not found: {excel_path}. Please provide path: python import_medicines_from_eml.py <path_to_excel>")
