import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from .db import get_conn
from .auth import roles_required

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

@hr_bp.route("/add", methods=["POST"])
@roles_required("admin", "hr")
def add():
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
            cur  = conn.execute("""
                INSERT INTO employees(name,dept,role,join_date,salary,pan,pf,esi)
                VALUES(?,?,?,?,?,?,?,?)
            """, (name, dept, role, join, float(salary), pan, pf, esi))
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
    return render_template("hr.html",
        employees=get_conn().execute("SELECT * FROM employees").fetchall(),
        errors=errors, form=f, q="", dept="")

@hr_bp.route("/delete/<int:emp_id>", methods=["POST"])
@roles_required("admin")
def delete(emp_id):
    conn = get_conn()
    conn.execute("UPDATE employees SET status='inactive' WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()
    flash("Employee marked inactive.", "info")
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
        conn.execute("""
            UPDATE employees SET name=?,dept=?,role=?,join_date=?,salary=?,pf=?,esi=?,status=?
            WHERE id=?
        """, (f["name"],f["dept"],f["role"],f["join_date"],float(f["salary"]),
              1 if f.get("pf") else 0, 1 if f.get("esi") else 0,
              f.get("status","active"), emp_id))
        conn.commit(); conn.close()
        flash("Employee updated.", "success")
        return redirect(url_for("hr.index"))
    conn.close()
    return render_template("hr_edit.html", emp=emp)
