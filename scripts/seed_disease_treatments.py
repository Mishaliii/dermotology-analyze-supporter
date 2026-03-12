import psycopg
import sys

# DB Config
DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13"
DB_NAME = "clinical_data"

def get_db_connection():
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    return psycopg.connect(conn_str)

def seed_disease_treatments():
    with get_db_connection() as conn:
        with conn.cursor() as cur:

            # Helper to get disease id (inserts if missing)
            def get_disease_id(name):
                cur.execute("SELECT id FROM diseases WHERE lower(name) = lower(%s)", (name,))
                res = cur.fetchone()
                if res:
                    return res[0]
                cur.execute("INSERT INTO diseases (name) VALUES (%s) RETURNING id", (name,))
                return cur.fetchone()[0]

            # Helper to get/insert medicine (exact name match, no wildcard)
            def get_medicine_id(name, generic="", category="", form="", strength=""):
                cur.execute("SELECT id FROM medicines WHERE lower(name) = lower(%s) LIMIT 1", (name,))
                res = cur.fetchone()
                if res:
                    return res[0]
                print(f"  Inserting missing medicine: {name}")
                cur.execute("""
                    INSERT INTO medicines (name, generic_name, category, form, strength, is_dermatology)
                    VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id
                """, (name, generic or name, category, form, strength))
                return cur.fetchone()[0]

            # ---------------------------------------------------------------
            # Treatment rules with CORRECT severity ranges per calculator:
            #
            # ACNE      -> GAGS score (0-44)
            #              0-10 Mild, 11-18 Moderate, 19-30 Severe, 31-44 Very Severe
            # PSORIASIS -> PASI score (0-72)
            #              0-5 Very Mild, 6-20 Mild-Moderate, 21-60 Severe, 61+ Very Severe
            # ECZEMA    -> EASI score (0-72)
            #              0-7 Clear, 8-21 Moderate, 22-50 Severe, 51+ Very Severe
            # VITILIGO  -> VASI score (0-10 typical)
            #              0-5 Focal, 6+ Widespread
            # ALOPECIA  -> SALT score (0-100%)
            #              0-50 Partial, 51-100 Extensive
            # ---------------------------------------------------------------

            rules = [
                # ---- Acne (GAGS 0–44) -----------------------------------------------
                {"disease": "Acne", "med": "Benzoyl Peroxide",
                 "generic": "Benzoyl Peroxide", "cat": "keratolytic",
                 "form": "gel", "strength": "2.5% / 5%",
                 "s_min": 0, "s_max": 10, "line": "First-line (Mild)"},

                {"disease": "Acne", "med": "Adapalene",
                 "generic": "Adapalene", "cat": "retinoid",
                 "form": "gel", "strength": "0.1%",
                 "s_min": 11, "s_max": 18, "line": "Second-line (Moderate)"},

                {"disease": "Acne", "med": "Doxycycline",
                 "generic": "Doxycycline", "cat": "antibiotic",
                 "form": "tablet", "strength": "100mg",
                 "s_min": 19, "s_max": 30, "line": "Third-line (Severe)"},

                {"disease": "Acne", "med": "Isotretinoin",
                 "generic": "Isotretinoin", "cat": "retinoid",
                 "form": "capsule", "strength": "10mg / 20mg",
                 "s_min": 31, "s_max": 44, "line": "Fourth-line (Cystic/Very Severe)"},

                # ---- Psoriasis (PASI 0–72) ------------------------------------------
                {"disease": "Psoriasis", "med": "White Soft Paraffin",
                 "generic": "White Soft Paraffin", "cat": "emollient",
                 "form": "ointment", "strength": "100%",
                 "s_min": 0, "s_max": 5, "line": "Maintenance / First-line"},

                {"disease": "Psoriasis", "med": "Betamethasone",
                 "generic": "Betamethasone Valerate", "cat": "corticosteroid",
                 "form": "ointment", "strength": "0.1%",
                 "s_min": 6, "s_max": 20, "line": "Topical First-line"},

                {"disease": "Psoriasis", "med": "Calcipotriol",
                 "generic": "Calcipotriol", "cat": "vitamin d analog",
                 "form": "ointment", "strength": "50mcg/g",
                 "s_min": 21, "s_max": 40, "line": "Second-line"},

                {"disease": "Psoriasis", "med": "Methotrexate",
                 "generic": "Methotrexate", "cat": "immunomodulator",
                 "form": "tablet", "strength": "2.5mg / 5mg",
                 "s_min": 41, "s_max": 60, "line": "Systemic Third-line"},

                {"disease": "Psoriasis", "med": "Adalimumab",
                 "generic": "Adalimumab", "cat": "biologic",
                 "form": "injection", "strength": "40mg/0.8ml",
                 "s_min": 61, "s_max": 72, "line": "Biologic / Severe"},

                # ---- Eczema / Atopic Dermatitis (EASI 0–72) -------------------------
                {"disease": "Eczema", "med": "Liquid Paraffin",
                 "generic": "Liquid Paraffin", "cat": "emollient",
                 "form": "cream", "strength": "Standard",
                 "s_min": 0, "s_max": 7, "line": "Maintenance"},

                {"disease": "Eczema", "med": "Hydrocortisone",
                 "generic": "Hydrocortisone", "cat": "corticosteroid",
                 "form": "cream", "strength": "1%",
                 "s_min": 8, "s_max": 21, "line": "Topical First-line"},

                {"disease": "Eczema", "med": "Tacrolimus",
                 "generic": "Tacrolimus", "cat": "immunomodulator",
                 "form": "ointment", "strength": "0.03% / 0.1%",
                 "s_min": 22, "s_max": 50, "line": "Second-line"},

                {"disease": "Eczema", "med": "Cyclosporine",
                 "generic": "Ciclosporin", "cat": "immunomodulator",
                 "form": "capsule", "strength": "25mg / 100mg",
                 "s_min": 51, "s_max": 72, "line": "Systemic / Severe"},

                # ---- Vitiligo (VASI 0–10 typical) -----------------------------------
                {"disease": "Vitiligo", "med": "Tacrolimus",
                 "generic": "Tacrolimus", "cat": "immunomodulator",
                 "form": "ointment", "strength": "0.1%",
                 "s_min": 0, "s_max": 5, "line": "First-line Topical"},

                {"disease": "Vitiligo", "med": "Clobetasol",
                 "generic": "Clobetasol Propionate", "cat": "corticosteroid",
                 "form": "cream", "strength": "0.05%",
                 "s_min": 6, "s_max": 100, "line": "Second-line Topical"},

                # ---- Alopecia (SALT 0–100%) -----------------------------------------
                {"disease": "Alopecia", "med": "Minoxidil",
                 "generic": "Minoxidil", "cat": "vasodilator",
                 "form": "solution", "strength": "2% / 5%",
                 "s_min": 0, "s_max": 50, "line": "First-line"},

                {"disease": "Alopecia", "med": "Finasteride",
                 "generic": "Finasteride",
                 "cat": "5-alpha reductase inhibitor",
                 "form": "tablet", "strength": "1mg",
                 "s_min": 51, "s_max": 100, "line": "Second-line"}
            ]

            # Clear old rules for diseases we are about to re-seed
            print("Seeding disease treatments (clearing old data first)...")
            touched_diseases = list(set(r["disease"] for r in rules))
            for dname in touched_diseases:
                d_id = get_disease_id(dname)
                cur.execute("DELETE FROM disease_treatments WHERE disease_id = %s", (d_id,))
                print(f"  Cleared old rules for: {dname}")

            count = 0
            for rule in rules:
                d_id = get_disease_id(rule["disease"])
                m_id = get_medicine_id(
                    rule["med"], rule.get("generic", ""),
                    rule["cat"], rule["form"], rule.get("strength", "")
                )
                cur.execute("""
                    INSERT INTO disease_treatments
                        (disease_id, medicine_id, severity_min, severity_max, line_of_therapy)
                    VALUES (%s, %s, %s, %s, %s)
                """, (d_id, m_id, rule["s_min"], rule["s_max"], rule["line"]))
                count += 1

            conn.commit()
            print(f"\nSuccessfully seeded {count} disease treatment rules.")

if __name__ == "__main__":
    seed_disease_treatments()
