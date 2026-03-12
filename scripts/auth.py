import hashlib
import psycopg

# DB Config — same as rest of the project
DB_HOST = "localhost"
DB_PORT = "5433"
DB_USER = "postgres"
DB_PASSWORD = "KL02@v13"
DB_NAME = "clinical_data"


def get_db_connection():
    conn_str = f"host={DB_HOST} port={DB_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"
    return psycopg.connect(conn_str)


def hash_password(plain: str) -> str:
    """
    SHA-256 hash of a plain-text password.
    Returns a 64-character hex string stored in the DB.
    No salt needed for an academic project; use bcrypt in production.
    """
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def signup_doctor(
    name: str,
    email: str,
    password: str,
    license_number: str = "",
    clinic_name: str = "",
) -> dict:
    """
    Register a new doctor account.
    Returns {success, doctor_id, name} or {success: False, error}.
    """
    email = email.strip().lower()
    if not name or not email or not password:
        return {"success": False, "error": "Name, email, and password are required."}

    pw_hash = hash_password(password)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check for duplicate email
                cur.execute("SELECT id FROM doctors WHERE lower(email) = %s", (email,))
                if cur.fetchone():
                    return {"success": False, "error": "Email already registered. Please log in."}

                cur.execute(
                    """
                    INSERT INTO doctors (name, email, license_number, clinic_name, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (name.strip(), email, license_number.strip(), clinic_name.strip(), pw_hash),
                )
                doctor_id = cur.fetchone()[0]
            conn.commit()

        return {"success": True, "doctor_id": doctor_id, "name": name.strip()}

    except Exception as e:
        return {"success": False, "error": str(e)}


def login_doctor(email: str, password: str) -> dict:
    """
    Authenticate a doctor by email + password.
    Returns {success, doctor_id, name} or {success: False, error}.
    """
    email = email.strip().lower()
    pw_hash = hash_password(password)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, password_hash FROM doctors WHERE lower(email) = %s",
                    (email,),
                )
                row = cur.fetchone()

        if not row:
            return {"success": False, "error": "Invalid email or password."}

        doctor_id, name, stored_hash = row

        if stored_hash is None:
            return {"success": False, "error": "Account has no password set. Please contact admin."}

        if stored_hash != pw_hash:
            return {"success": False, "error": "Invalid email or password."}

        return {"success": True, "doctor_id": doctor_id, "name": name}

    except Exception as e:
        return {"success": False, "error": str(e)}
