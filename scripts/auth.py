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


def _get_doctors_columns(cur) -> set:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'doctors'
        """
    )
    return {row[0] for row in cur.fetchall()}


def _is_admin(cur, doctor_id: int) -> bool:
    cur.execute(
        """
        SELECT COALESCE(is_admin, FALSE)
        FROM doctors
        WHERE id = %s
        """,
        (doctor_id,),
    )
    row = cur.fetchone()
    return bool(row and row[0])


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
                doctors_columns = _get_doctors_columns(cur)

                # Check for duplicate email and return a user-friendly pending message.
                if "approved" in doctors_columns:
                    cur.execute(
                        """
                        SELECT id, COALESCE(approved, FALSE)
                        FROM doctors
                        WHERE lower(email) = %s
                        LIMIT 1
                        """,
                        (email,),
                    )
                    existing = cur.fetchone()
                    if existing:
                        if not bool(existing[1]):
                            return {
                                "success": False,
                                "error": "A registration request with this email is already pending approval. No need to request access again.",
                                "pending": True,
                            }
                        return {"success": False, "error": "Email already registered. Please log in."}
                else:
                    cur.execute("SELECT id FROM doctors WHERE lower(email) = %s", (email,))
                    if cur.fetchone():
                        return {"success": False, "error": "Email already registered. Please log in."}

                insert_cols = ["name", "email", "license_number", "clinic_name", "password_hash"]
                insert_vals = [name.strip(), email, license_number.strip(), clinic_name.strip(), pw_hash]

                # New registrations are pending by default in admin-enabled schemas.
                if "approved" in doctors_columns:
                    insert_cols.append("approved")
                    insert_vals.append(False)
                if "is_admin" in doctors_columns:
                    insert_cols.append("is_admin")
                    insert_vals.append(False)

                placeholders = ", ".join(["%s"] * len(insert_cols))
                sql = f"INSERT INTO doctors ({', '.join(insert_cols)}) VALUES ({placeholders}) RETURNING id"
                cur.execute(sql, tuple(insert_vals))
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
                doctors_columns = _get_doctors_columns(cur)

                select_cols = ["id", "name", "password_hash"]
                if "is_admin" in doctors_columns:
                    select_cols.append("is_admin")
                if "approved" in doctors_columns:
                    select_cols.append("approved")

                cur.execute(
                    f"SELECT {', '.join(select_cols)} FROM doctors WHERE lower(email) = %s",
                    (email,),
                )
                row = cur.fetchone()

        if not row:
            return {"success": False, "error": "Invalid email or password."}

        doctor_id = row[0]
        name = row[1]
        stored_hash = row[2]

        col_idx = 3
        is_admin = False
        approved = True
        if "is_admin" in doctors_columns:
            is_admin = bool(row[col_idx])
            col_idx += 1
        if "approved" in doctors_columns:
            approved = bool(row[col_idx])

        if stored_hash is None:
            return {"success": False, "error": "Account has no password set. Please contact admin."}

        if stored_hash != pw_hash:
            return {"success": False, "error": "Invalid email or password."}

        # Keep success=true so frontend can show a pending-approval state cleanly.
        if not approved and not is_admin:
            return {
                "success": True,
                "doctor_id": doctor_id,
                "doctor_name": name,
                "name": name,
                "is_admin": False,
                "approved": False,
            }

        return {
            "success": True,
            "doctor_id": doctor_id,
            "doctor_name": name,
            "name": name,
            "is_admin": is_admin,
            "approved": True,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_pending_doctors(admin_doctor_id: int) -> dict:
    """Return all doctors awaiting approval (admin only)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                doctors_columns = _get_doctors_columns(cur)
                if "is_admin" not in doctors_columns or "approved" not in doctors_columns:
                    return {"success": False, "error": "Admin workflow is not enabled in database schema."}

                if not _is_admin(cur, admin_doctor_id):
                    return {"success": False, "error": "Admin access required."}

                cur.execute(
                    """
                    SELECT id, name, email, clinic_name, license_number, created_at
                    FROM doctors
                    WHERE COALESCE(approved, FALSE) = FALSE
                      AND COALESCE(is_admin, FALSE) = FALSE
                    ORDER BY created_at DESC, id DESC
                    """
                )
                rows = cur.fetchall()

        doctors = [
            {
                "id": r[0],
                "name": r[1] or "",
                "email": r[2] or "",
                "specialization": r[3] or "",
                "license_number": r[4] or "",
                "created_at": str(r[5]) if r[5] else "",
            }
            for r in rows
        ]
        return {"success": True, "doctors": doctors}
    except Exception as e:
        return {"success": False, "error": str(e)}


def approve_doctor(admin_doctor_id: int, doctor_id: int) -> dict:
    """Approve a pending doctor account (admin only)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                doctors_columns = _get_doctors_columns(cur)
                if "is_admin" not in doctors_columns or "approved" not in doctors_columns:
                    return {"success": False, "error": "Admin workflow is not enabled in database schema."}

                if not _is_admin(cur, admin_doctor_id):
                    return {"success": False, "error": "Admin access required."}

                cur.execute(
                    """
                    UPDATE doctors
                    SET approved = TRUE
                    WHERE id = %s AND COALESCE(is_admin, FALSE) = FALSE
                    """,
                    (doctor_id,),
                )
                updated = cur.rowcount
            conn.commit()

        if not updated:
            return {"success": False, "error": "Doctor not found or cannot be approved."}
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def reject_doctor(admin_doctor_id: int, doctor_id: int) -> dict:
    """Reject a pending doctor account by deleting it (admin only)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                doctors_columns = _get_doctors_columns(cur)
                if "is_admin" not in doctors_columns or "approved" not in doctors_columns:
                    return {"success": False, "error": "Admin workflow is not enabled in database schema."}

                if not _is_admin(cur, admin_doctor_id):
                    return {"success": False, "error": "Admin access required."}

                cur.execute(
                    """
                    DELETE FROM doctors
                    WHERE id = %s
                      AND COALESCE(is_admin, FALSE) = FALSE
                      AND COALESCE(approved, FALSE) = FALSE
                    """,
                    (doctor_id,),
                )
                deleted = cur.rowcount
            conn.commit()

        if not deleted:
            return {"success": False, "error": "Doctor not found or not pending."}
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_doctors(admin_doctor_id: int) -> dict:
    """Return all registered doctors (admin only)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                doctors_columns = _get_doctors_columns(cur)
                if "is_admin" not in doctors_columns or "approved" not in doctors_columns:
                    return {"success": False, "error": "Admin workflow is not enabled in database schema."}

                if not _is_admin(cur, admin_doctor_id):
                    return {"success": False, "error": "Admin access required."}

                cur.execute(
                    """
                    SELECT id, name, email, license_number, clinic_name,
                           COALESCE(is_admin, FALSE), COALESCE(approved, FALSE), created_at
                    FROM doctors
                    ORDER BY COALESCE(is_admin, FALSE) DESC, created_at DESC, id DESC
                    """
                )
                rows = cur.fetchall()

        return {
            "success": True,
            "doctors": [
                {
                    "id": r[0],
                    "name": r[1] or "",
                    "email": r[2] or "",
                    "license_number": r[3] or "",
                    "clinic_name": r[4] or "",
                    "is_admin": bool(r[5]),
                    "approved": bool(r[6]),
                    "created_at": str(r[7]) if r[7] else "",
                }
                for r in rows
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_doctor_by_admin(
    admin_doctor_id: int,
    name: str,
    email: str,
    password: str,
    license_number: str = "",
    clinic_name: str = "",
    is_admin: bool = False,
    approved: bool = True,
) -> dict:
    """Create a doctor account directly from admin panel."""
    email = (email or "").strip().lower()
    name = (name or "").strip()

    if not name or not email or not password:
        return {"success": False, "error": "Name, email, and password are required."}

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                doctors_columns = _get_doctors_columns(cur)
                if "is_admin" not in doctors_columns or "approved" not in doctors_columns:
                    return {"success": False, "error": "Admin workflow is not enabled in database schema."}

                if not _is_admin(cur, admin_doctor_id):
                    return {"success": False, "error": "Admin access required."}

                cur.execute("SELECT id FROM doctors WHERE lower(email) = %s", (email,))
                if cur.fetchone():
                    return {"success": False, "error": "Email already registered."}

                cur.execute(
                    """
                    INSERT INTO doctors (name, email, license_number, clinic_name, password_hash, is_admin, approved)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        name,
                        email,
                        (license_number or "").strip(),
                        (clinic_name or "").strip(),
                        hash_password(password),
                        bool(is_admin),
                        bool(approved) or bool(is_admin),
                    ),
                )
                doctor_id = cur.fetchone()[0]
            conn.commit()

        return {"success": True, "doctor_id": doctor_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_doctor_by_admin(
    admin_doctor_id: int,
    doctor_id: int,
    name: str = "",
    email: str = "",
    license_number: str = "",
    clinic_name: str = "",
    is_admin: bool = False,
    approved: bool = True,
    password: str = "",
) -> dict:
    """Update an existing doctor's details (admin only)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                doctors_columns = _get_doctors_columns(cur)
                if "is_admin" not in doctors_columns or "approved" not in doctors_columns:
                    return {"success": False, "error": "Admin workflow is not enabled in database schema."}

                if not _is_admin(cur, admin_doctor_id):
                    return {"success": False, "error": "Admin access required."}

                if admin_doctor_id == doctor_id and not is_admin:
                    return {"success": False, "error": "You cannot remove your own admin role."}

                updates = [
                    "name = %s",
                    "email = %s",
                    "license_number = %s",
                    "clinic_name = %s",
                    "is_admin = %s",
                    "approved = %s",
                ]
                values = [
                    (name or "").strip(),
                    (email or "").strip().lower(),
                    (license_number or "").strip(),
                    (clinic_name or "").strip(),
                    bool(is_admin),
                    bool(approved) or bool(is_admin),
                ]

                if (password or "").strip():
                    updates.append("password_hash = %s")
                    values.append(hash_password(password.strip()))

                values.append(doctor_id)

                cur.execute(
                    f"UPDATE doctors SET {', '.join(updates)} WHERE id = %s",
                    tuple(values),
                )
                updated = cur.rowcount
            conn.commit()

        if not updated:
            return {"success": False, "error": "Doctor not found."}
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_doctor_by_admin(admin_doctor_id: int, doctor_id: int) -> dict:
    """Delete a doctor account (admin only)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                doctors_columns = _get_doctors_columns(cur)
                if "is_admin" not in doctors_columns or "approved" not in doctors_columns:
                    return {"success": False, "error": "Admin workflow is not enabled in database schema."}

                if not _is_admin(cur, admin_doctor_id):
                    return {"success": False, "error": "Admin access required."}

                if admin_doctor_id == doctor_id:
                    return {"success": False, "error": "You cannot delete your own admin account."}

                cur.execute("SELECT COALESCE(is_admin, FALSE) FROM doctors WHERE id = %s", (doctor_id,))
                target = cur.fetchone()
                if not target:
                    return {"success": False, "error": "Doctor not found."}
                if bool(target[0]):
                    return {"success": False, "error": "Admin accounts cannot be deleted."}

                cur.execute("DELETE FROM doctors WHERE id = %s", (doctor_id,))
                deleted = cur.rowcount
            conn.commit()

        if not deleted:
            return {"success": False, "error": "Doctor not found."}
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
