from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from .db import get_conn
from datetime import date, timedelta

timesheet_bp = Blueprint("timesheet", __name__)

def week_range(offset=0):
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    return monday, monday + timedelta(days=6)

@login_required
@timesheet_bp.route("/")
def index():
    offset = int(request.args.get("week", 0))
    emp_filter = request.args.get("emp", "")
    start, end = week_range(offset)

    conn      = get_conn()
    is_manager = current_user.role in ("admin", "hr")

    # Non-managers only see themselves
    if is_manager:
        employees = conn.execute("SELECT id, name FROM employees WHERE status='active'").fetchall()
    else:
        employees = conn.execute(
            "SELECT id, name FROM employees WHERE id=? AND status='active'",
            (current_user.employee_id,)
        ).fetchall()

    projects  = conn.execute("SELECT id, name FROM projects WHERE status='active'").fetchall()

    sql = """
        SELECT t.*, e.name as emp_name, p.name as proj_name
        FROM timesheets t
        JOIN employees e ON e.id=t.employee_id
        JOIN projects  p ON p.id=t.project_id
        WHERE t.work_date BETWEEN ? AND ?
    """
    params = [str(start), str(end)]

    # Lock non-managers to their own employee_id
    if not is_manager:
        sql += " AND t.employee_id=?"; params.append(current_user.employee_id)
    elif emp_filter:
        sql += " AND t.employee_id=?"; params.append(emp_filter)

    sql += " ORDER BY t.work_date, e.name"
    entries = conn.execute(sql, params).fetchall()
    conn.close()

    # Build week grid: {emp_id: {day_offset: hours}}
    grid = {}
    for e in entries:
        eid = e["employee_id"]
        d   = date.fromisoformat(e["work_date"])
        day = (d - start).days
        grid.setdefault(eid, {}).setdefault(day, 0)
        grid[eid][day] += e["hours"]

    days = [(start + timedelta(days=i)).strftime("%a %d") for i in range(7)]
    return render_template("timesheet.html",
        employees=employees, projects=projects,
        entries=entries, grid=grid, days=days,
        week_start=start, week_end=end,
        offset=offset, emp_filter=emp_filter,
        is_manager=is_manager,
        my_emp_id=current_user.employee_id)

@login_required
@timesheet_bp.route("/add", methods=["POST"])
def add():
    f = request.form
    emp_id  = f.get("employee_id")
    proj_id = f.get("project_id")
    wdate   = f.get("work_date")
    hours   = f.get("hours")
    notes   = f.get("notes","").strip()
    offset  = f.get("offset", 0)

    if not all([emp_id, proj_id, wdate, hours]):
        flash("All fields are required.", "error")
    else:
        conn = get_conn()
        conn.execute("""
            INSERT INTO timesheets(employee_id,project_id,work_date,hours,notes)
            VALUES(?,?,?,?,?)
        """, (emp_id, proj_id, wdate, float(hours), notes))
        conn.commit()
        conn.close()
        flash("Entry logged.", "success")

    return redirect(url_for("timesheet.index", week=offset))

@login_required
@timesheet_bp.route("/delete/<int:tid>", methods=["POST"])
def delete(tid):
    conn = get_conn()
    conn.execute("DELETE FROM timesheets WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    flash("Entry removed.", "info")
    return redirect(url_for("timesheet.index"))
