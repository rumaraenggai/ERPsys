from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .db import get_conn
import hashlib

projects_bp = Blueprint("projects", __name__)

def gen_id(name):
    return "P" + str(int(hashlib.md5(name.encode()).hexdigest(), 16) % 900 + 100)

def _all_employees(conn):
    return conn.execute("SELECT id, name FROM employees WHERE status='active' ORDER BY name").fetchall()


# ── Index ─────────────────────────────────────────────────────────────────────

@login_required
@projects_bp.route("/")
def index():
    conn   = get_conn()
    status = request.args.get("status", "")
    sql    = "SELECT * FROM projects"
    params = []
    if status:
        sql += " WHERE status=?"; params.append(status)
    projects  = conn.execute(sql, params).fetchall()
    employees = _all_employees(conn)   # needed for Add Project lead/members dropdowns
    conn.close()
    return render_template("projects.html", projects=projects,
                           employees=employees, status=status)


# ── Add project ───────────────────────────────────────────────────────────────

@login_required
@projects_bp.route("/add", methods=["POST"])
def add():
    f        = request.form
    errors   = {}
    name     = f.get("name",        "").strip()
    client   = f.get("client",      "").strip()
    start    = f.get("start_date",  "").strip()
    end      = f.get("end_date",    "").strip()
    budget   = f.get("budget",      "").strip()
    lead     = f.get("lead",        "").strip()
    ptype    = f.get("type",        "")
    billing  = f.get("billing_type","Fixed price")
    status   = f.get("status",      "active")
    members  = request.form.getlist("members")   # user-selected, may be empty
    ms_names = request.form.getlist("ms_name")
    ms_dates = request.form.getlist("ms_date")

    if not name:   errors["name"]   = "Project name required"
    if not client: errors["client"] = "Client required"
    if not start:  errors["start"]  = "Start date required"
    if not end:    errors["end"]    = "End date required"
    elif start and end < start: errors["end"] = "End must be after start"
    if not budget or not budget.replace(".", "").isdigit():
        errors["budget"] = "Valid budget required"
    if not lead:   errors["lead"]   = "Project lead required"

    if errors:
        flash("Please fix the errors below.", "error")
        conn      = get_conn()
        projects  = conn.execute("SELECT * FROM projects").fetchall()
        employees = _all_employees(conn)
        conn.close()
        return render_template("projects.html",
            projects=projects, employees=employees,
            errors=errors, form=f, show_form=True, status="")

    pid  = gen_id(name)
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO projects
            (id,name,client,type,status,start_date,end_date,budget,lead,billing_type)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (pid, name, client, ptype, status, start, end, float(budget), lead, billing))

    # Only insert explicitly chosen members — no automatic population
    for emp_id in members:
        conn.execute(
            "INSERT OR IGNORE INTO project_members(project_id,employee_id) VALUES(?,?)",
            (pid, emp_id)
        )

    for ms_name, ms_date in zip(ms_names, ms_dates):
        if ms_name.strip():
            conn.execute(
                "INSERT INTO milestones(project_id,name,due_date) VALUES(?,?,?)",
                (pid, ms_name.strip(), ms_date)
            )

    conn.commit()
    conn.close()
    flash(f"Project '{name}' created (ID: {pid}).", "success")
    return redirect(url_for("projects.detail", pid=pid))


# ── Members ───────────────────────────────────────────────────────────────────

@login_required
@projects_bp.route("/detail/<pid>/members/add", methods=["POST"])
def member_add(pid):
    emp_id = request.form.get("employee_id")
    if emp_id:
        conn = get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO project_members(project_id,employee_id) VALUES(?,?)",
            (pid, emp_id)
        )
        conn.commit(); conn.close()
        flash("Member added.", "success")
    return redirect(url_for("projects.detail", pid=pid))


@login_required
@projects_bp.route("/detail/<pid>/members/remove", methods=["POST"])
def member_remove(pid):
    emp_id = request.form.get("employee_id")
    if emp_id:
        conn = get_conn()
        conn.execute(
            "DELETE FROM project_members WHERE project_id=? AND employee_id=?",
            (pid, emp_id)
        )
        conn.commit(); conn.close()
        flash("Member removed.", "info")
    return redirect(url_for("projects.detail", pid=pid))


# ── Activities ────────────────────────────────────────────────────────────────

@login_required
@projects_bp.route("/detail/<pid>/activities/add", methods=["POST"])
def activity_add(pid):
    name = request.form.get("activity_name", "").strip()
    if not name:
        flash("Activity name is required.", "error")
        return redirect(url_for("projects.detail", pid=pid))
    conn = get_conn()
    conn.execute(
        "INSERT INTO project_activities(project_id, name) VALUES(?,?)", (pid, name)
    )
    conn.commit(); conn.close()
    flash(f"Activity '{name}' added.", "success")
    return redirect(url_for("projects.detail", pid=pid))


@login_required
@projects_bp.route("/detail/<pid>/activities/delete", methods=["POST"])
def activity_delete(pid):
    act_id = request.form.get("activity_id")
    conn   = get_conn()
    conn.execute(
        "DELETE FROM project_activities WHERE id=? AND project_id=?", (act_id, pid)
    )
    conn.commit(); conn.close()
    flash("Activity removed.", "info")
    return redirect(url_for("projects.detail", pid=pid))


# ── API: activities for a project (used by timesheet JS dropdown) ─────────────

@projects_bp.route("/api/<pid>/activities")
@login_required
def api_activities(pid):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name FROM project_activities WHERE project_id=? ORDER BY name",
        (pid,)
    ).fetchall()
    conn.close()
    return jsonify([{"id": r["id"], "name": r["name"]} for r in rows])


# ── Detail ────────────────────────────────────────────────────────────────────

@login_required
@projects_bp.route("/detail/<pid>")
def detail(pid):
    conn       = get_conn()
    project    = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    milestones = conn.execute(
        "SELECT * FROM milestones WHERE project_id=?", (pid,)
    ).fetchall()
    members    = conn.execute("""
        SELECT e.* FROM employees e
        JOIN project_members pm ON pm.employee_id=e.id
        WHERE pm.project_id=?
    """, (pid,)).fetchall()
    activities = conn.execute(
        "SELECT * FROM project_activities WHERE project_id=? ORDER BY name", (pid,)
    ).fetchall()
    timesheets = conn.execute("""
        SELECT t.*, e.name as emp_name,
               COALESCE(pa.name, '-') as activity_name
        FROM timesheets t
        JOIN employees e ON e.id=t.employee_id
        LEFT JOIN project_activities pa ON pa.id=t.activity_id
        WHERE t.project_id=? ORDER BY t.work_date DESC
    """, (pid,)).fetchall()
    # Employees not yet in this project (for the Add Member dropdown)
    member_ids  = [m["id"] for m in members]
    non_members = [e for e in _all_employees(conn) if e["id"] not in member_ids]
    conn.close()
    return render_template("project_detail.html",
        project=project, milestones=milestones,
        members=members, non_members=non_members,
        activities=activities, timesheets=timesheets)
