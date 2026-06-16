from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from .db import get_conn
import hashlib

projects_bp = Blueprint("projects", __name__)

def gen_id(name):
    return "P" + str(int(hashlib.md5(name.encode()).hexdigest(), 16) % 900 + 100)

@login_required
@projects_bp.route("/")
def index():
    conn = get_conn()
    status = request.args.get("status", "")
    sql = "SELECT * FROM projects"
    params = []
    if status:
        sql += " WHERE status=?"; params.append(status)
    projects = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template("projects.html", projects=projects, status=status)

@login_required
@projects_bp.route("/add", methods=["POST"])
def add():
    f = request.form
    errors = {}
    name    = f.get("name","").strip()
    client  = f.get("client","").strip()
    start   = f.get("start_date","").strip()
    end     = f.get("end_date","").strip()
    budget  = f.get("budget","").strip()
    lead    = f.get("lead","").strip()
    ptype   = f.get("type","")
    billing = f.get("billing_type","Fixed price")
    status  = f.get("status","active")
    members = request.form.getlist("members")
    ms_names = request.form.getlist("ms_name")
    ms_dates = request.form.getlist("ms_date")

    if not name:   errors["name"]   = "Project name required"
    if not client: errors["client"] = "Client required"
    if not start:  errors["start"]  = "Start date required"
    if not end:    errors["end"]    = "End date required"
    elif start and end < start: errors["end"] = "End must be after start"
    if not budget or not budget.replace(".","").isdigit():
                   errors["budget"] = "Valid budget required"
    if not lead:   errors["lead"]   = "Project lead required"

    if errors:
        flash("Please fix the errors below.", "error")
        conn = get_conn()
        employees = conn.execute("SELECT * FROM employees WHERE status='active'").fetchall()
        conn.close()
        return render_template("projects.html",
            projects=get_conn().execute("SELECT * FROM projects").fetchall(),
            employees=employees, errors=errors, form=f, show_form=True, status="")

    pid = gen_id(name)
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO projects(id,name,client,type,status,start_date,end_date,budget,lead,billing_type)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (pid, name, client, ptype, status, start, end, float(budget), lead, billing))

    for emp_id in members:
        conn.execute("INSERT INTO project_members(project_id,employee_id) VALUES(?,?)", (pid, emp_id))

    for ms_name, ms_date in zip(ms_names, ms_dates):
        if ms_name.strip():
            conn.execute("INSERT INTO milestones(project_id,name,due_date) VALUES(?,?,?)", (pid, ms_name.strip(), ms_date))

    conn.commit()
    conn.close()
    flash(f"Project '{name}' created (ID: {pid}).", "success")
    return redirect(url_for("projects.index"))

@login_required
@projects_bp.route("/detail/<pid>")
def detail(pid):
    conn = get_conn()
    project    = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    milestones = conn.execute("SELECT * FROM milestones WHERE project_id=?", (pid,)).fetchall()
    members    = conn.execute("""
        SELECT e.* FROM employees e
        JOIN project_members pm ON pm.employee_id=e.id
        WHERE pm.project_id=?
    """, (pid,)).fetchall()
    timesheets = conn.execute("""
        SELECT t.*, e.name as emp_name FROM timesheets t
        JOIN employees e ON e.id=t.employee_id
        WHERE t.project_id=? ORDER BY t.work_date DESC
    """, (pid,)).fetchall()
    conn.close()
    return render_template("project_detail.html",
        project=project, milestones=milestones,
        members=members, timesheets=timesheets)
