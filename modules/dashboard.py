from flask import Blueprint, render_template
from flask_login import login_required, current_user
from .db import get_conn
from datetime import date

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def index():
    conn  = get_conn()
    today = str(date.today())
    year  = date.today().year
    month = date.today().month
    emp_id = current_user.employee_id

    # Metrics
    total_emp   = conn.execute("SELECT COUNT(*) FROM employees WHERE status='active'").fetchone()[0]
    present     = conn.execute("SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE punch_date=?", (today,)).fetchone()[0]
    active_proj = conn.execute("SELECT COUNT(*) FROM projects WHERE status='active'").fetchone()[0]
    payroll     = conn.execute("SELECT SUM(salary) FROM employees WHERE status='active'").fetchone()[0] or 0
    open_leaves = conn.execute("SELECT COUNT(*) FROM leave_requests WHERE status='pending'").fetchone()[0]
    open_tasks  = conn.execute("SELECT COUNT(*) FROM tasks WHERE status != 'done'").fetchone()[0]

    # My tasks (for non-admin)
    my_tasks = []
    if emp_id:
        my_tasks = conn.execute("""
            SELECT t.*, p.name as proj_name FROM tasks t
            JOIN projects p ON p.id=t.project_id
            WHERE t.assigned_to=? AND t.status != 'done'
            ORDER BY t.due_date LIMIT 5
        """, (emp_id,)).fetchall()

    # Recent leave requests (for hr/admin)
    recent_leaves = conn.execute("""
        SELECT r.*, e.name as emp_name, lt.name as leave_name
        FROM leave_requests r
        JOIN employees e ON e.id=r.employee_id
        JOIN leave_types lt ON lt.id=r.leave_type_id
        WHERE r.status='pending'
        ORDER BY r.applied_on DESC LIMIT 5
    """).fetchall()

    # Project burn
    projects = conn.execute("""
        SELECT name, budget, spent FROM projects
        WHERE status='active' AND budget > 0
        ORDER BY (spent*1.0/budget) DESC LIMIT 4
    """).fetchall()

    conn.close()
    return render_template("dashboard.html",
        total_emp=total_emp, present=present,
        active_proj=active_proj, payroll=payroll,
        open_leaves=open_leaves, open_tasks=open_tasks,
        my_tasks=my_tasks, recent_leaves=recent_leaves,
        projects=projects, today=today)
