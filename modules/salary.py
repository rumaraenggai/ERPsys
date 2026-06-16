from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from .db import get_conn
from datetime import date

salary_bp = Blueprint("salary", __name__)

def calc_salary(emp, year, month):
    gross  = emp["salary"]
    basic  = round(gross * 0.50)
    hra    = round(gross * 0.20)
    special = gross - basic - hra

    pf  = round(min(basic, 15000) * 0.12) if emp["pf"]  else 0
    esi = round(gross * 0.0075)            if emp["esi"] else 0
    pt  = 200  # Professional Tax (Maharashtra flat rate)

    annual_taxable = (gross - pf - esi) * 12
    tds = round(max(0, annual_taxable - 250000) * 0.10 / 12)

    total_ded = pf + esi + pt + tds
    net       = gross - total_ded

    # Attendance-adjusted working days
    conn = get_conn()
    att = conn.execute("""
        SELECT COUNT(*) as days FROM attendance
        WHERE employee_id=? AND strftime('%Y',punch_date)=? AND strftime('%m',punch_date)=?
    """, (emp["id"], str(year), f"{month:02d}")).fetchone()
    conn.close()
    worked_days = att["days"] if att else "—"

    return dict(
        gross=gross, basic=basic, hra=hra, special=special,
        pf=pf, esi=esi, pt=pt, tds=tds,
        total_ded=total_ded, net=net, worked_days=worked_days
    )

@login_required
@salary_bp.route("/")
def index():
    today  = date.today()
    year   = int(request.args.get("year",  today.year))
    month  = int(request.args.get("month", today.month))
    emp_id = request.args.get("emp_id")

    conn      = get_conn()
    employees = conn.execute("SELECT * FROM employees WHERE status='active'").fetchall()
    conn.close()

    selected = None
    slip     = None
    if emp_id:
        conn     = get_conn()
        selected = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
        conn.close()
        if selected:
            slip = calc_salary(selected, year, month)

    return render_template("salary.html",
        employees=employees, selected=selected,
        slip=slip, year=year, month=month,
        months=["Jan","Feb","Mar","Apr","May","Jun",
                "Jul","Aug","Sep","Oct","Nov","Dec"])

@salary_bp.route("/pdf")
@login_required
def pdf():
    from flask import send_file, abort
    from .pdf_payslip import generate_payslip
    emp_id = request.args.get("emp_id")
    year   = int(request.args.get("year",  date.today().year))
    month  = int(request.args.get("month", date.today().month))
    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    if not emp_id:
        abort(400, "emp_id required")

    conn = get_conn()
    emp  = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    conn.close()
    if not emp:
        abort(404, "Employee not found")

    slip = calc_salary(emp, year, month)
    buf  = generate_payslip(emp, slip, year, month, MONTHS[month-1])
    filename = f"Payslip_{emp['name'].replace(' ','_')}_{MONTHS[month-1]}{year}.pdf"
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)

@salary_bp.route("/export/excel")
@login_required
def export_excel():
    from flask import send_file
    from .excel_payroll import generate_payroll_register
    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    year   = int(request.args.get("year",  date.today().year))
    month  = int(request.args.get("month", date.today().month))

    conn      = get_conn()
    employees = conn.execute("SELECT * FROM employees WHERE status='active'").fetchall()
    conn.close()

    buf      = generate_payroll_register(employees, calc_salary, year, month, MONTHS[month-1])
    filename = f"Payroll_Register_{MONTHS[month-1]}{year}.xlsx"
    return send_file(buf,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=filename)

@salary_bp.route("/email/config", methods=["POST"])
@login_required
def save_smtp():
    from .auth import roles_required
    if current_user.role not in ("admin", "hr"):
        flash("Only HR/Admin can configure email settings.", "error")
        return redirect(url_for("salary.index"))
    f = request.form
    conn = get_conn()
    conn.execute("""
        INSERT INTO smtp_config(id, sender, password)
        VALUES(1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET sender=excluded.sender, password=excluded.password
    """, (f.get("sender","").strip(), f.get("password","").strip()))
    conn.commit()
    conn.close()
    flash("SMTP settings saved.", "success")
    return redirect(url_for("salary.index", emp_id=f.get("emp_id"),
                            year=f.get("year"), month=f.get("month")))

@salary_bp.route("/email/send", methods=["POST"])
@login_required
def send_email():
    from .pdf_payslip import generate_payslip
    from .email_dispatch import send_payslip_email
    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    f      = request.form
    emp_id = f.get("emp_id")
    year   = int(f.get("year",  date.today().year))
    month  = int(f.get("month", date.today().month))
    to_email = f.get("to_email","").strip()

    conn = get_conn()
    emp  = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    cfg  = conn.execute("SELECT * FROM smtp_config WHERE id=1").fetchone()
    conn.close()

    if not emp:
        flash("Employee not found.", "error")
        return redirect(url_for("salary.index"))
    if not cfg or not cfg["sender"] or not cfg["password"]:
        flash("SMTP not configured. Please save email settings first.", "error")
        return redirect(url_for("salary.index", emp_id=emp_id, year=year, month=month))
    if not to_email:
        flash("Recipient email is required.", "error")
        return redirect(url_for("salary.index", emp_id=emp_id, year=year, month=month))

    slip     = calc_salary(emp, year, month)
    mn       = MONTHS[month-1]
    pdf_buf  = generate_payslip(emp, slip, year, month, mn)
    filename = f"Payslip_{emp['name'].replace(' ','_')}_{mn}{year}.pdf"

    try:
        send_payslip_email(cfg["sender"], cfg["password"],
                           to_email, emp["name"], mn, year, pdf_buf, filename)
        flash(f"Payslip emailed to {to_email}.", "success")
    except Exception as e:
        flash(f"Email failed: {e}", "error")

    return redirect(url_for("salary.index", emp_id=emp_id, year=year, month=month))
