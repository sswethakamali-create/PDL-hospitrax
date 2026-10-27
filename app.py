from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import uuid
import os
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# FLASK CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "hospitrax_secret_key_2026"
)


# =========================================================
# DATABASE
# =========================================================

DATABASE = "hospitrax.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

def create_tables():

    conn = get_db()

    # -----------------------------------------------------
    # PATIENTS
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            upid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            blood_group TEXT NOT NULL,
            phone TEXT NOT NULL,
            hospital TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # MEDICAL RECORDS
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS medical_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upid TEXT NOT NULL,
            hospital TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            treatment TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (upid)
                REFERENCES patients(upid)
                ON DELETE CASCADE
        )
    """)

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            upid TEXT
        )
    """)

    # -----------------------------------------------------
    # DOCTORS
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            phone TEXT,
            hospital TEXT
        )
    """)

    # -----------------------------------------------------
    # HOSPITALS
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            phone TEXT
        )
    """)

    # -----------------------------------------------------
    # BEDS
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS beds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital TEXT NOT NULL,
            bed_number TEXT NOT NULL,
            ward TEXT,
            status TEXT NOT NULL DEFAULT 'Available'
        )
    """)

    # =====================================================
    # DEFAULT ADMIN
    # =====================================================

    admin = conn.execute(
        "SELECT id FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if not admin:

        conn.execute("""
            INSERT INTO users
            (username, password, role, upid)
            VALUES (?, ?, ?, ?)
        """, (
            "admin",
            generate_password_hash("admin123"),
            "admin",
            None
        ))

    # =====================================================
    # DEFAULT DOCTOR
    # =====================================================

    doctor = conn.execute(
        "SELECT id FROM users WHERE username = ?",
        ("doctor",)
    ).fetchone()

    if not doctor:

        conn.execute("""
            INSERT INTO users
            (username, password, role, upid)
            VALUES (?, ?, ?, ?)
        """, (
            "doctor",
            generate_password_hash("doctor123"),
            "doctor",
            None
        ))

    # =====================================================
    # CREATE LOGIN FOR EXISTING PATIENTS
    # =====================================================

    patients = conn.execute("""
        SELECT *
        FROM patients
    """).fetchall()

    for patient in patients:

        existing_user = conn.execute(
            """
            SELECT id
            FROM users
            WHERE upid = ?
            """,
            (patient["upid"],)
        ).fetchone()

        if not existing_user:

            conn.execute("""
                INSERT INTO users
                (username, password, role, upid)
                VALUES (?, ?, ?, ?)
            """, (
                patient["upid"],
                generate_password_hash(patient["phone"]),
                "patient",
                patient["upid"]
            ))

    conn.commit()
    conn.close()


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return decorated_function


# =========================================================
# ROLE REQUIRED
# =========================================================

def role_required(*allowed_roles):

    def decorator(function):

        @wraps(function)
        def decorated_function(*args, **kwargs):

            if "user_id" not in session:
                return redirect(url_for("login"))

            if session.get("role") not in allowed_roles:
                return "Access Denied", 403

            return function(*args, **kwargs)

        return decorated_function

    return decorator


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:

            return render_template(
                "login.html",
                error="Please enter username and password."
            )

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["upid"] = user["upid"]

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password."
        )

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    role = session.get("role")

    # =====================================================
    # ADMIN DASHBOARD
    # =====================================================

    if role == "admin":

        conn = get_db()

        total_patients = conn.execute(
            "SELECT COUNT(*) FROM patients"
        ).fetchone()[0]

        total_doctors = conn.execute(
            "SELECT COUNT(*) FROM doctors"
        ).fetchone()[0]

        total_hospitals = conn.execute(
            "SELECT COUNT(*) FROM hospitals"
        ).fetchone()[0]

        total_records = conn.execute(
            "SELECT COUNT(*) FROM medical_records"
        ).fetchone()[0]

        total_beds = conn.execute(
            "SELECT COUNT(*) FROM beds"
        ).fetchone()[0]

        available_beds = conn.execute("""
            SELECT COUNT(*)
            FROM beds
            WHERE status = 'Available'
        """).fetchone()[0]

        occupied_beds = conn.execute("""
            SELECT COUNT(*)
            FROM beds
            WHERE status = 'Occupied'
        """).fetchone()[0]

        conn.close()

        return render_template(
            "admin.html",
            username=session.get("username"),
            role=role,
            total_patients=total_patients,
            total_doctors=total_doctors,
            total_hospitals=total_hospitals,
            total_records=total_records,
            total_beds=total_beds,
            available_beds=available_beds,
            occupied_beds=occupied_beds
        )

    # =====================================================
    # DOCTOR DASHBOARD
    # =====================================================

    elif role == "doctor":

        return render_template(
            "doctor.html",
            username=session.get("username"),
            role=role
        )

    # =====================================================
    # PATIENT DASHBOARD
    # =====================================================

    elif role == "patient":

        upid = session.get("upid")

        conn = get_db()

        patient = None
        records = []

        if upid:

            patient = conn.execute("""
                SELECT *
                FROM patients
                WHERE upid = ?
            """, (upid,)).fetchone()

            records = conn.execute("""
                SELECT *
                FROM medical_records
                WHERE upid = ?
                ORDER BY id DESC
            """, (upid,)).fetchall()

        conn.close()

        return render_template(
            "patient.html",
            username=session.get("username"),
            role=role,
            patient=patient,
            records=records
        )

    return redirect(url_for("logout"))


# =========================================================
# PATIENT REGISTRATION
# =========================================================

@app.route("/register", methods=["POST"])
@login_required
@role_required("admin", "doctor")
def register():

    name = request.form.get(
        "name",
        ""
    ).strip()

    age = request.form.get(
        "age",
        ""
    ).strip()

    gender = request.form.get(
        "gender",
        ""
    ).strip()

    blood_group = request.form.get(
        "blood_group",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    hospital = request.form.get(
        "hospital",
        ""
    ).strip()

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not all([
        name,
        age,
        gender,
        blood_group,
        phone,
        hospital
    ]):

        return render_template(
            "index.html",
            error_message="All patient fields are required.",
            logged_in=True,
            username=session.get("username"),
            role=session.get("role")
        )

    try:

        age = int(age)

        if age <= 0 or age > 120:
            raise ValueError

    except ValueError:

        return render_template(
            "index.html",
            error_message="Please enter a valid age.",
            logged_in=True,
            username=session.get("username"),
            role=session.get("role")
        )

    # -----------------------------------------------------
    # GENERATE UPID
    # -----------------------------------------------------

    upid = "HOS-" + str(uuid.uuid4())[:8].upper()

    conn = get_db()

    try:

        # -------------------------------------------------
        # INSERT PATIENT
        # -------------------------------------------------

        conn.execute("""
            INSERT INTO patients
            (
                upid,
                name,
                age,
                gender,
                blood_group,
                phone,
                hospital
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            upid,
            name,
            age,
            gender,
            blood_group,
            phone,
            hospital
        ))

        # -------------------------------------------------
        # CREATE PATIENT LOGIN
        # -------------------------------------------------

        conn.execute("""
            INSERT INTO users
            (
                username,
                password,
                role,
                upid
            )
            VALUES (?, ?, ?, ?)
        """, (
            upid,
            generate_password_hash(phone),
            "patient",
            upid
        ))

        conn.commit()

    except sqlite3.Error as error:

        conn.rollback()
        conn.close()

        return render_template(
            "index.html",
            error_message=f"Registration failed: {error}",
            logged_in=True,
            username=session.get("username"),
            role=session.get("role")
        )

    conn.close()

    return render_template(
        "index.html",
        success=True,
        upid=upid,
        name=name,
        hospital=hospital,
        patient_username=upid,
        patient_password=phone,
        logged_in=True,
        username=session.get("username"),
        role=session.get("role")
    )


# =========================================================
# PATIENT SEARCH
# =========================================================

@app.route("/search", methods=["POST"])
@login_required
def search():

    upid = request.form.get(
        "upid",
        ""
    ).strip().upper()

    if not upid:

        return render_template(
            "index.html",
            search_error=True,
            error_message="Please enter a UPID.",
            logged_in=True,
            username=session.get("username"),
            role=session.get("role")
        )

    # -----------------------------------------------------
    # PATIENT CAN ONLY ACCESS OWN RECORD
    # -----------------------------------------------------

    if session.get("role") == "patient":

        if session.get("upid") != upid:

            return render_template(
                "index.html",
                search_error=True,
                searched_upid=upid,
                error_message=(
                    "You can only access your own medical records."
                ),
                logged_in=True,
                username=session.get("username"),
                role=session.get("role")
            )

    conn = get_db()

    patient = conn.execute("""
        SELECT *
        FROM patients
        WHERE upid = ?
    """, (upid,)).fetchone()

    records = conn.execute("""
        SELECT *
        FROM medical_records
        WHERE upid = ?
        ORDER BY id DESC
    """, (upid,)).fetchall()

    conn.close()

    if patient:

        return render_template(
            "index.html",
            patient=patient,
            records=records,
            search_success=True,
            logged_in=True,
            username=session.get("username"),
            role=session.get("role")
        )

    return render_template(
        "index.html",
        search_error=True,
        searched_upid=upid,
        error_message="Patient not found.",
        logged_in=True,
        username=session.get("username"),
        role=session.get("role")
    )


# =========================================================
# ADD MEDICAL RECORD
# =========================================================

@app.route("/add_record", methods=["POST"])
@login_required
@role_required("admin", "doctor")
def add_record():

    upid = request.form.get(
        "upid",
        ""
    ).strip().upper()

    hospital = request.form.get(
        "hospital",
        ""
    ).strip()

    diagnosis = request.form.get(
        "diagnosis",
        ""
    ).strip()

    treatment = request.form.get(
        "treatment",
        ""
    ).strip()

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not all([
        upid,
        hospital,
        diagnosis,
        treatment
    ]):

        return render_template(
            "index.html",
            error_message="All medical record fields are required.",
            logged_in=True,
            username=session.get("username"),
            role=session.get("role")
        )

    conn = get_db()

    # -----------------------------------------------------
    # CHECK PATIENT
    # -----------------------------------------------------

    patient = conn.execute("""
        SELECT *
        FROM patients
        WHERE upid = ?
    """, (upid,)).fetchone()

    if not patient:

        conn.close()

        return render_template(
            "index.html",
            search_error=True,
            searched_upid=upid,
            error_message="Patient with this UPID does not exist.",
            logged_in=True,
            username=session.get("username"),
            role=session.get("role")
        )

    # -----------------------------------------------------
    # ADD MEDICAL RECORD
    # -----------------------------------------------------

    date = datetime.now().strftime("%d-%m-%Y")

    conn.execute("""
        INSERT INTO medical_records
        (
            upid,
            hospital,
            diagnosis,
            treatment,
            date
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        upid,
        hospital,
        diagnosis,
        treatment,
        date
    ))

    conn.commit()

    conn.close()

    # =====================================================
    # IMPORTANT
    # AFTER SAVING RECORD:
    # DOCTOR -> DOCTOR DASHBOARD
    # ADMIN  -> ADMIN DASHBOARD
    # =====================================================

    return redirect(url_for("dashboard"))


# =========================================================
# ADMIN - PATIENTS
# =========================================================

@app.route("/admin/patients")
@login_required
@role_required("admin")
def admin_patients():

    conn = get_db()

    patients = conn.execute("""
        SELECT *
        FROM patients
        ORDER BY name
    """).fetchall()

    conn.close()

    return render_template(
        "patients.html",
        patients=patients,
        username=session.get("username"),
        role=session.get("role")
    )


# =========================================================
# ADMIN - DOCTORS
# =========================================================

@app.route("/admin/doctors")
@login_required
@role_required("admin")
def admin_doctors():

    conn = get_db()

    doctors = conn.execute("""
        SELECT *
        FROM doctors
        ORDER BY name
    """).fetchall()

    conn.close()

    return render_template(
        "doctors.html",
        doctors=doctors,
        username=session.get("username"),
        role=session.get("role")
    )


# =========================================================
# ADMIN - HOSPITALS
# =========================================================

@app.route("/admin/hospitals")
@login_required
@role_required("admin")
def admin_hospitals():

    conn = get_db()

    hospitals = conn.execute("""
        SELECT *
        FROM hospitals
        ORDER BY name
    """).fetchall()

    conn.close()

    return render_template(
        "hospitals.html",
        hospitals=hospitals,
        username=session.get("username"),
        role=session.get("role")
    )


# =========================================================
# ADMIN - BEDS
# =========================================================

@app.route("/admin/beds")
@login_required
@role_required("admin")
def admin_beds():

    conn = get_db()

    beds = conn.execute("""
        SELECT *
        FROM beds
        ORDER BY hospital, bed_number
    """).fetchall()

    conn.close()

    return render_template(
        "beds.html",
        beds=beds,
        username=session.get("username"),
        role=session.get("role")
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    create_tables()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )