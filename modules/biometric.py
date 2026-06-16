from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .db import get_conn
from datetime import date

biometric_bp = Blueprint("biometric", __name__)

@login_required
@biometric_bp.route("/")
def index():
    today = str(date.today())
    conn  = get_conn()
    records = conn.execute("""
        SELECT a.*, e.name as emp_name
        FROM attendance a JOIN employees e ON e.id=a.employee_id
        WHERE a.punch_date=?
        ORDER BY a.punch_in
    """, (today,)).fetchall()
    employees = conn.execute("SELECT id, name FROM employees WHERE status='active'").fetchall()
    conn.close()
    return render_template("biometric.html", records=records, employees=employees, today=today)

@login_required
@biometric_bp.route("/sync", methods=["POST"])
def sync():
    """
    Pull live attendance from ESSL device using pyzk.
    Install: pip install pyzk
    Device must be on the same LAN (default port 4370).
    """
    ip   = request.form.get("ip",   "192.168.1.100")
    port = int(request.form.get("port", 4370))
    try:
        from zk import ZK
        zk   = ZK(ip, port=port, timeout=5)
        conn_zk = zk.connect()
        conn_zk.disable_device()
        attendances = conn_zk.get_attendance()
        conn_zk.enable_device()
        conn_zk.disconnect()

        db   = get_conn()
        saved = 0
        for a in attendances:
            emp = db.execute("SELECT id FROM employees WHERE name LIKE ?",
                             (f"%{a.user_id}%",)).fetchone()
            if not emp:
                continue
            punch_date = a.timestamp.strftime("%Y-%m-%d")
            punch_time = a.timestamp.strftime("%H:%M")
            existing   = db.execute("""
                SELECT id FROM attendance
                WHERE employee_id=? AND punch_date=? AND punch_in=?
            """, (emp["id"], punch_date, punch_time)).fetchone()
            if not existing:
                db.execute("""
                    INSERT INTO attendance(employee_id,punch_date,punch_in,source)
                    VALUES(?,?,?,'essl')
                """, (emp["id"], punch_date, punch_time))
                saved += 1
        db.commit()
        db.close()
        flash(f"Sync complete — {saved} new records imported from {ip}.", "success")
    except ImportError:
        flash("pyzk not installed. Run: pip install pyzk", "error")
    except Exception as e:
        flash(f"Sync failed: {e}", "error")

    return redirect(url_for("biometric.index"))

@login_required
@biometric_bp.route("/manual", methods=["POST"])
def manual():
    f       = request.form
    emp_id  = f.get("employee_id")
    pdate   = f.get("punch_date")
    pin     = f.get("punch_in")
    pout    = f.get("punch_out", "")
    if not all([emp_id, pdate, pin]):
        flash("Employee, date and punch-in are required.", "error")
        return redirect(url_for("biometric.index"))
    conn = get_conn()
    conn.execute("""
        INSERT INTO attendance(employee_id,punch_date,punch_in,punch_out,source)
        VALUES(?,?,?,?,'manual')
    """, (emp_id, pdate, pin, pout or None))
    conn.commit()
    conn.close()
    flash("Manual punch recorded.", "success")
    return redirect(url_for("biometric.index"))
