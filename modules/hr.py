

import re
import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from .db import get_conn
from .auth import roles_required

ALLOWED_EXTENSIONS = {"pdf","png","jpg","jpeg","docx","xlsx","txt"}
DOC_TYPES = ["Offer Letter","Appointment Letter","ID Proof","Address Proof",
             "Educational Certificate","Experience Letter","PAN Card",
             "Aadhaar Card","Passport","Photo","Contract","Other"]

# Extended employee profile fields — all optional, form field name == db column name
EXTENDED_FIELDS = [
    "file_no", "employee_code",
    "dob", "age", "blood_group", "probation_period", "confirmation_date", "notice_period",
    "personal_contact", "personal_email", "official_email",
    "current_address", "permanent_address",
    "offer_letter", "aadhar_card", "pan_card_note", "insurance_list",
    "account_number", "ifsc_code",
    "edu_ssc", "edu_hsc", "edu_ug", "edu_pg",
    "emergency_name", "emergency_relation", "emergency_contact", "emergency_location",
    "father_name", "father_contact",
    "mother_name", "mother_contact",
    "sister_name", "sister_contact",
    "brother_name", "brother_contact",
]

def _allowed(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS

hr_bp = Blueprint("hr", __name__)

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

@hr_bp.route("/")
@login_required
def index():
    conn = get_conn()
    q        = request.args.get("q", "").strip()
    dept     = request.args.get("dept", "")
    show_all = request.args.get("show_all", "")
    sql      = "SELECT * FROM employees WHERE 1=1"
    params   = []
    if not show_all:
        sql += " AND status != 'inactive'"
    if q:
        sql += " AND name LIKE ?"; params.append(f"%{q}%")
    if dept:
        sql += " AND dept=?"; params.append(dept)
    employees = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template("hr.html", employees=employees, q=q, dept=dept, show_all=show_all)

@hr_bp.route("/add", methods=["GET", "POST"])
@roles_required("admin", "hr")
def add():
    if request.method == "GET":
        return render_template("hr_add.html", errors=None, form=None)

    f = request.form
    errors = {}
    name    = f.get("name", "").strip()
    dept    = f.get("dept", "").strip()
    role    = f.get("role", "").strip()
    join    = f.get("join_date", "").strip()
    salary  = f.get("salary", "").strip()
    pan     = f.get("pan", "").strip().upper()
    pf      = 1 if f.get("pf") else 0
    esi     = 1 if f.get("esi") else 0

    if not name:   errors["name"]   = "Name is required"
    if not dept:   errors["dept"]   = "Department is required"
    if not role:   errors["role"]   = "Role is required"
    if not join:   errors["join"]   = "Joining date is required"
    if not salary or not salary.replace(".","").isdigit():
                   errors["salary"] = "Valid salary required"
    if not pan:    errors["pan"]    = "PAN is required"
    elif not PAN_RE.match(pan): errors["pan"] = "Invalid PAN format"

    if not errors:
        try:
            import bcrypt as _bcrypt
            conn = get_conn()

            ext_cols = ", ".join(EXTENDED_FIELDS)
            ext_qs   = ", ".join(["?"] * len(EXTENDED_FIELDS))
            ext_vals = [f.get(col, "").strip() or None for col in EXTENDED_FIELDS]

            cur  = conn.execute(f"""
                INSERT INTO employees(name,dept,role,join_date,salary,pan,pf,esi,{ext_cols})
                VALUES(?,?,?,?,?,?,?,?,{ext_qs})
            """, (name, dept, role, join, float(salary), pan, pf, esi, *ext_vals))
            emp_id = cur.lastrowid

            # Auto-create login: username = firstname.lastname (lowercase)
            parts    = name.lower().split()
            username = parts[0] + ("." + parts[-1] if len(parts) > 1 else "")
            # Default password = PAN (lowercase) — user should change on first login
            raw_pw   = pan.lower()
            hashed   = _bcrypt.hashpw(raw_pw.encode(), _bcrypt.gensalt()).decode()
            # Handle duplicate usernames by appending emp_id
            try:
                conn.execute("""
                    INSERT INTO users(username,password,full_name,role,employee_id)
                    VALUES(?,?,?,'user',?)
                """, (username, hashed, name, emp_id))
            except Exception:
                conn.execute("""
                    INSERT INTO users(username,password,full_name,role,employee_id)
                    VALUES(?,?,?,'user',?)
                """, (f"{username}{emp_id}", hashed, name, emp_id))

            conn.commit()
            conn.close()
            flash(f"{name} added. Login: {username} / Password: {pan.lower()} (share securely — employee should change it).", "success")
            return redirect(url_for("hr.index"))
        except Exception as e:
            if "UNIQUE" in str(e):
                errors["pan"] = "PAN already exists"

    flash("Please fix the errors below.", "error")
    return render_template("hr_add.html", errors=errors, form=f)

@hr_bp.route("/delete/<int:emp_id>", methods=["POST"])
@roles_required("admin")
def delete(emp_id):
    conn = get_conn()
    conn.execute("UPDATE employees SET status='inactive' WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()
    flash("Employee marked inactive.", "info")
    return redirect(url_for("hr.index"))

@hr_bp.route("/permadelete/<int:emp_id>", methods=["POST"])
@roles_required("admin")
def permadelete(emp_id):
    """Permanently remove an employee and all dependent records. Cannot be undone."""
    conn = get_conn()
    emp  = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not emp:
        flash("Employee not found.", "error")
        conn.close()
        return redirect(url_for("hr.index"))

    # Remove uploaded document files from disk
    docs = conn.execute("SELECT stored_name FROM employee_documents WHERE employee_id=?", (emp_id,)).fetchall()
    for d in docs:
        fpath = os.path.join(current_app.config["UPLOAD_FOLDER"], d["stored_name"])
        if os.path.exists(fpath):
            os.remove(fpath)

    conn.execute("DELETE FROM employee_documents WHERE employee_id=?", (emp_id,))
    conn.execute("DELETE FROM users WHERE employee_id=?", (emp_id,))
    conn.execute("DELETE FROM attendance WHERE employee_id=?", (emp_id,))
    conn.execute("DELETE FROM leave_balances WHERE employee_id=?", (emp_id,))
    conn.execute("DELETE FROM leave_requests WHERE employee_id=?", (emp_id,))
    conn.execute("DELETE FROM timesheets WHERE employee_id=?", (emp_id,))
    conn.execute("DELETE FROM project_members WHERE employee_id=?", (emp_id,))
    conn.execute("DELETE FROM employees WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()
    flash(f"{emp['name']} permanently deleted.", "info")
    return redirect(url_for("hr.index"))

@hr_bp.route("/edit/<int:emp_id>", methods=["GET","POST"])
@roles_required("admin","hr")
def edit(emp_id):
    conn = get_conn()
    emp  = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not emp:
        flash("Employee not found.", "error")
        return redirect(url_for("hr.index"))
    if request.method == "POST":
        f = request.form
        ext_sets = ", ".join([f"{col}=?" for col in EXTENDED_FIELDS])
        ext_vals = [f.get(col, "").strip() or None for col in EXTENDED_FIELDS]
        conn.execute(f"""
            UPDATE employees SET name=?,dept=?,role=?,join_date=?,salary=?,pf=?,esi=?,status=?,{ext_sets}
            WHERE id=?
        """, (f["name"],f["dept"],f["role"],f["join_date"],float(f["salary"]),
              1 if f.get("pf") else 0, 1 if f.get("esi") else 0,
              f.get("status","active"), *ext_vals, emp_id))
        conn.commit(); conn.close()
        flash("Employee updated.", "success")
        return redirect(url_for("hr.index"))
    conn.close()
    return render_template("hr_edit.html", emp=emp)

# ── Document Management ──────────────────────────────────────

@hr_bp.route("/<int:emp_id>/documents")
@login_required
def documents(emp_id):
    conn = get_conn()
    emp  = conn.execute("SELECT id,name FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not emp:
        abort(404)
    docs = conn.execute(
        "SELECT * FROM employee_documents WHERE employee_id=? ORDER BY uploaded_on DESC",
        (emp_id,)
    ).fetchall()
    conn.close()
    return render_template("hr_documents.html", emp=emp, docs=docs, doc_types=DOC_TYPES)

@hr_bp.route("/<int:emp_id>/documents/upload", methods=["POST"])
@roles_required("admin","hr")
def upload_document(emp_id):
    file     = request.files.get("file")
    doc_type = request.form.get("doc_type","Other").strip()
    notes    = request.form.get("notes","").strip()

    if not file or file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("hr.documents", emp_id=emp_id))
    if not _allowed(file.filename):
        flash(f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}", "error")
        return redirect(url_for("hr.documents", emp_id=emp_id))

    # Store with UUID to avoid collisions
    ext         = file.filename.rsplit(".",1)[1].lower()
    stored_name = f"{emp_id}_{uuid.uuid4().hex}.{ext}"
    save_path   = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)
    file.save(save_path)

    conn = get_conn()
    conn.execute("""
        INSERT INTO employee_documents(employee_id,doc_type,filename,stored_name,uploaded_by,notes)
        VALUES(?,?,?,?,?,?)
    """, (emp_id, doc_type, file.filename, stored_name, current_user.full_name, notes))
    conn.commit(); conn.close()
    flash(f"'{file.filename}' uploaded successfully.", "success")
    return redirect(url_for("hr.documents", emp_id=emp_id))

@hr_bp.route("/<int:emp_id>/documents/download/<int:doc_id>")
@login_required
def download_document(emp_id, doc_id):
    conn = get_conn()
    doc  = conn.execute(
        "SELECT * FROM employee_documents WHERE id=? AND employee_id=?",
        (doc_id, emp_id)
    ).fetchone()
    conn.close()
    if not doc:
        abort(404)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        doc["stored_name"],
        as_attachment=True,
        download_name=doc["filename"]
    )

@hr_bp.route("/<int:emp_id>/documents/delete/<int:doc_id>", methods=["POST"])
@roles_required("admin","hr")
def delete_document(emp_id, doc_id):
    conn = get_conn()
    doc  = conn.execute(
        "SELECT * FROM employee_documents WHERE id=? AND employee_id=?",
        (doc_id, emp_id)
    ).fetchone()
    if doc:
        # Remove file from disk
        fpath = os.path.join(current_app.config["UPLOAD_FOLDER"], doc["stored_name"])
        if os.path.exists(fpath):
            os.remove(fpath)
        conn.execute("DELETE FROM employee_documents WHERE id=?", (doc_id,))
        conn.commit()
        flash("Document deleted.", "info")
    conn.close()
    return redirect(url_for("hr.documents", emp_id=emp_id))

