from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .db import get_conn

tasks_bp = Blueprint("tasks", __name__)

@tasks_bp.route("/")
@login_required
def index():
    conn = get_conn()
    proj_filter = request.args.get("project", "")
    is_manager  = current_user.role in ("admin", "hr")

    sql = """
        SELECT t.*, p.name as proj_name, e.name as assignee_name
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        LEFT JOIN employees e ON e.id = t.assigned_to
        WHERE 1=1
    """
    params = []
    if not is_manager and current_user.employee_id:
        sql += " AND t.assigned_to=?"; params.append(current_user.employee_id)
    if proj_filter:
        sql += " AND t.project_id=?"; params.append(proj_filter)
    sql += " ORDER BY t.due_date, p.name"
    tasks    = conn.execute(sql, params).fetchall()
    projects = conn.execute("SELECT id,name FROM projects WHERE status='active'").fetchall()
    employees= conn.execute("SELECT id,name FROM employees WHERE status='active'").fetchall()
    conn.close()
    return render_template("tasks.html", tasks=tasks, projects=projects,
                           employees=employees, proj_filter=proj_filter,
                           is_manager=is_manager)

@tasks_bp.route("/add", methods=["POST"])
@login_required
def add():
    f = request.form
    proj = f.get("project_id","").strip()
    title= f.get("title","").strip()
    if not proj or not title:
        flash("Project and title are required.", "error")
        return redirect(url_for("tasks.index"))
    conn = get_conn()
    conn.execute("""
        INSERT INTO tasks(project_id, title, assigned_to, due_date, status)
        VALUES(?,?,?,?,?)
    """, (proj, title, f.get("assigned_to") or None,
          f.get("due_date") or None, f.get("status","open")))
    conn.commit(); conn.close()
    flash(f"Task '{title}' created.", "success")
    return redirect(url_for("tasks.index"))

@tasks_bp.route("/status/<int:tid>", methods=["POST"])
@login_required
def update_status(tid):
    new_status = request.form.get("status","open")
    conn = get_conn()
    conn.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, tid))
    conn.commit(); conn.close()
    flash("Task updated.", "success")
    return redirect(url_for("tasks.index"))

@tasks_bp.route("/delete/<int:tid>", methods=["POST"])
@login_required
def delete(tid):
    if current_user.role not in ("admin","hr"):
        flash("Not authorised.", "error")
        return redirect(url_for("tasks.index"))
    conn = get_conn()
    conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
    conn.commit(); conn.close()
    flash("Task deleted.", "info")
    return redirect(url_for("tasks.index"))
