from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from .db import get_conn
from datetime import date, datetime

leave_bp = Blueprint("leave", __name__)

def _working_days(from_date, to_date):
    """Count Mon–Sat between two dates (excluding Sundays)."""
    from datetime import timedelta
    d, count = datetime.strptime(from_date, "%Y-%m-%d").date(), 0
    end = datetime.strptime(to_date, "%Y-%m-%d").date()
    while d <= end:
        if d.weekday() != 6:   # 6 = Sunday
            count += 1
        d += timedelta(days=1)
    return count

def _ensure_balance(conn, emp_id, lt_id, year, allocated):
    """Create balance row if missing (e.g. new employee or new leave type)."""
    conn.execute("""
        INSERT OR IGNORE INTO leave_balances(employee_id,leave_type_id,year,allocated,used)
        VALUES(?,?,?,?,0)
    """, (emp_id, lt_id, year, allocated))

@leave_bp.route("/")
@login_required
def index():
    conn = get_conn()
    emp_filter = request.args.get("emp", "")
    status_filter = request.args.get("status", "")
    year = int(request.args.get("year", date.today().year))

    sql = """
        SELECT r.*, e.name as emp_name, lt.name as leave_name, lt.paid
        FROM leave_requests r
        JOIN employees e  ON e.id  = r.employee_id
        JOIN leave_types lt ON lt.id = r.leave_type_id
        WHERE 1=1
    """
    params = []
    if emp_filter:
        sql += " AND r.employee_id=?"; params.append(emp_filter)
    if status_filter:
        sql += " AND r.status=?"; params.append(status_filter)
    sql += " ORDER BY r.applied_on DESC"

    requests_ = conn.execute(sql, params).fetchall()
    employees  = conn.execute("SELECT id, name FROM employees WHERE status='active'").fetchall()
    leave_types = conn.execute("SELECT * FROM leave_types").fetchall()

    # Balances for summary card
    balances = conn.execute("""
        SELECT lb.*, e.name as emp_name, lt.name as leave_name
        FROM leave_balances lb
        JOIN employees e   ON e.id  = lb.employee_id
        JOIN leave_types lt ON lt.id = lb.leave_type_id
        WHERE lb.year=?
        ORDER BY e.name, lt.name
    """, (year,)).fetchall()

    conn.close()
    return render_template("leave.html",
        requests=requests_, employees=employees,
        leave_types=leave_types, balances=balances,
        emp_filter=emp_filter, status_filter=status_filter,
        year=year, today=str(date.today()))

@leave_bp.route("/apply", methods=["POST"])
@login_required
def apply():
    f         = request.form
    emp_id    = f.get("employee_id")
    lt_id     = f.get("leave_type_id")
    from_date = f.get("from_date")
    to_date   = f.get("to_date")
    reason    = f.get("reason", "").strip()

    if not all([emp_id, lt_id, from_date, to_date]):
        flash("All fields are required.", "error")
        return redirect(url_for("leave.index"))
    if to_date < from_date:
        flash("End date must be on or after start date.", "error")
        return redirect(url_for("leave.index"))

    days = _working_days(from_date, to_date)
    year = int(from_date[:4])

    conn = get_conn()
    lt   = conn.execute("SELECT * FROM leave_types WHERE id=?", (lt_id,)).fetchone()
    _ensure_balance(conn, emp_id, lt_id, year, lt["days"])

    bal = conn.execute("""
        SELECT * FROM leave_balances
        WHERE employee_id=? AND leave_type_id=? AND year=?
    """, (emp_id, lt_id, year)).fetchone()

    available = (bal["allocated"] - bal["used"]) if bal else 0
    if lt["paid"] and days > available:
        flash(f"Insufficient balance. Available: {available:.0f} days, Requested: {days} days.", "error")
        conn.close()
        return redirect(url_for("leave.index"))

    conn.execute("""
        INSERT INTO leave_requests(employee_id,leave_type_id,from_date,to_date,days,reason)
        VALUES(?,?,?,?,?,?)
    """, (emp_id, lt_id, from_date, to_date, days, reason))
    conn.commit()
    conn.close()
    flash(f"Leave application submitted — {days} working day(s).", "success")
    return redirect(url_for("leave.index"))

@leave_bp.route("/review/<int:req_id>", methods=["POST"])
@login_required
def review(req_id):
    from .auth import roles_required
    if current_user.role not in ("admin", "hr"):
        flash("Only HR/Admin can approve or reject leave.", "error")
        return redirect(url_for("leave.index"))

    action  = request.form.get("action")   # approve | reject
    remarks = request.form.get("remarks", "").strip()
    today   = str(date.today())

    conn = get_conn()
    req  = conn.execute("SELECT * FROM leave_requests WHERE id=?", (req_id,)).fetchone()
    if not req:
        flash("Request not found.", "error")
        conn.close()
        return redirect(url_for("leave.index"))

    new_status = "approved" if action == "approve" else "rejected"
    conn.execute("""
        UPDATE leave_requests
        SET status=?, reviewed_by=?, reviewed_on=?, remarks=?
        WHERE id=?
    """, (new_status, current_user.full_name, today, remarks, req_id))

    # Deduct balance on approval
    if new_status == "approved":
        year = int(req["from_date"][:4])
        _ensure_balance(conn, req["employee_id"], req["leave_type_id"], year, 0)
        conn.execute("""
            UPDATE leave_balances SET used = used + ?
            WHERE employee_id=? AND leave_type_id=? AND year=?
        """, (req["days"], req["employee_id"], req["leave_type_id"], year))

    conn.commit()
    conn.close()
    flash(f"Leave {new_status}.", "success")
    return redirect(url_for("leave.index"))

@leave_bp.route("/cancel/<int:req_id>", methods=["POST"])
@login_required
def cancel(req_id):
    conn = get_conn()
    req  = conn.execute("SELECT * FROM leave_requests WHERE id=?", (req_id,)).fetchone()
    if req and req["status"] == "approved":
        year = int(req["from_date"][:4])
        conn.execute("""
            UPDATE leave_balances SET used = MAX(0, used - ?)
            WHERE employee_id=? AND leave_type_id=? AND year=?
        """, (req["days"], req["employee_id"], req["leave_type_id"], year))
    conn.execute("UPDATE leave_requests SET status='cancelled' WHERE id=?", (req_id,))
    conn.commit()
    conn.close()
    flash("Leave cancelled.", "info")
    return redirect(url_for("leave.index"))
