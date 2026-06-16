from flask import Blueprint, render_template, request, send_file
from flask_login import login_required, current_user
from .db import get_conn
from .salary import calc_salary
from datetime import date
import io

reports_bp = Blueprint("reports", __name__)
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

@reports_bp.route("/")
@login_required
def index():
    today = date.today()
    return render_template("reports.html", year=today.year, month=today.month, months=MONTHS)

@reports_bp.route("/attendance")
@login_required
def attendance():
    year  = int(request.args.get("year",  date.today().year))
    month = int(request.args.get("month", date.today().month))
    conn  = get_conn()
    rows  = conn.execute("""
        SELECT e.name, e.dept,
               COUNT(DISTINCT a.punch_date) as days_present,
               SUM(CASE WHEN time(a.punch_in) > time('09:30') THEN 1 ELSE 0 END) as late_count,
               ROUND(SUM(
                 CASE WHEN a.punch_out IS NOT NULL
                 THEN (strftime('%H',a.punch_out)*60 + strftime('%M',a.punch_out) -
                       strftime('%H',a.punch_in)*60  - strftime('%M',a.punch_in)) / 60.0
                 ELSE 0 END
               ),1) as total_hours
        FROM employees e
        LEFT JOIN attendance a ON a.employee_id=e.id
            AND strftime('%Y',a.punch_date)=? AND strftime('%m',a.punch_date)=?
        WHERE e.status='active'
        GROUP BY e.id ORDER BY e.name
    """, (str(year), f"{month:02d}")).fetchall()
    conn.close()
    return render_template("reports.html", report="attendance", rows=rows,
                           year=year, month=month, months=MONTHS,
                           month_name=MONTHS[month-1])

@reports_bp.route("/payroll")
@login_required
def payroll():
    if current_user.role not in ("admin","hr"):
        from flask import abort; abort(403)
    year  = int(request.args.get("year",  date.today().year))
    month = int(request.args.get("month", date.today().month))
    conn  = get_conn()
    employees = conn.execute("SELECT * FROM employees WHERE status='active'").fetchall()
    conn.close()
    rows = [(emp, calc_salary(emp, year, month)) for emp in employees]
    total_gross = sum(r[1]["gross"] for r in rows)
    total_net   = sum(r[1]["net"]   for r in rows)
    total_ded   = sum(r[1]["total_ded"] for r in rows)
    return render_template("reports.html", report="payroll", rows=rows,
                           year=year, month=month, months=MONTHS,
                           month_name=MONTHS[month-1],
                           total_gross=total_gross, total_net=total_net, total_ded=total_ded)

@reports_bp.route("/compliance")
@login_required
def compliance():
    if current_user.role not in ("admin","hr"):
        from flask import abort; abort(403)
    year  = int(request.args.get("year",  date.today().year))
    month = int(request.args.get("month", date.today().month))
    conn  = get_conn()
    employees = conn.execute("SELECT * FROM employees WHERE status='active' AND pf=1").fetchall()
    conn.close()
    rows = []
    for emp in employees:
        slip = calc_salary(emp, year, month)
        rows.append({
            "name": emp["name"], "dept": emp["dept"],
            "gross": slip["gross"], "basic": slip["basic"],
            "pf_emp": slip["pf"], "pf_er": round(min(slip["basic"],15000)*0.12),
            "esi_emp": slip["esi"] if emp["esi"] else 0,
            "esi_er":  round(slip["gross"]*0.0325) if emp["esi"] else 0,
            "pt": slip["pt"], "tds": slip["tds"],
        })
    return render_template("reports.html", report="compliance", rows=rows,
                           year=year, month=month, months=MONTHS,
                           month_name=MONTHS[month-1])

@reports_bp.route("/timesheet-summary")
@login_required
def timesheet_summary():
    year  = int(request.args.get("year",  date.today().year))
    month = int(request.args.get("month", date.today().month))
    conn  = get_conn()
    rows  = conn.execute("""
        SELECT e.name, e.dept, p.name as proj_name,
               SUM(t.hours) as total_hours, COUNT(*) as entries
        FROM timesheets t
        JOIN employees e ON e.id=t.employee_id
        JOIN projects  p ON p.id=t.project_id
        WHERE strftime('%Y',t.work_date)=? AND strftime('%m',t.work_date)=?
        GROUP BY e.id, p.id ORDER BY e.name, p.name
    """, (str(year), f"{month:02d}")).fetchall()
    conn.close()
    return render_template("reports.html", report="timesheet_summary", rows=rows,
                           year=year, month=month, months=MONTHS,
                           month_name=MONTHS[month-1])

@reports_bp.route("/export/payroll-excel")
@login_required
def export_payroll_excel():
    if current_user.role not in ("admin","hr"):
        from flask import abort; abort(403)
    from .excel_payroll import generate_payroll_register
    year  = int(request.args.get("year",  date.today().year))
    month = int(request.args.get("month", date.today().month))
    conn  = get_conn()
    employees = conn.execute("SELECT * FROM employees WHERE status='active'").fetchall()
    conn.close()
    buf  = generate_payroll_register(employees, calc_salary, year, month, MONTHS[month-1])
    fname = f"Payroll_Register_{MONTHS[month-1]}{year}.xlsx"
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=fname)
