from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from .db import get_conn
from datetime import date

holidays_bp = Blueprint("holidays", __name__)

@holidays_bp.route("/")
@login_required
def index():
    year = int(request.args.get("year", date.today().year))
    conn = get_conn()
    holidays = conn.execute(
        "SELECT * FROM holidays WHERE year=? ORDER BY date", (year,)
    ).fetchall()
    conn.close()
    return render_template("holidays.html", holidays=holidays, year=year)

@holidays_bp.route("/add", methods=["POST"])
@login_required
def add():
    if current_user.role not in ("admin","hr"):
        flash("Not authorised.", "error")
        return redirect(url_for("holidays.index"))
    name = request.form.get("name","").strip()
    dt   = request.form.get("date","").strip()
    if not name or not dt:
        flash("Name and date are required.", "error")
        return redirect(url_for("holidays.index"))
    year = int(dt[:4])
    conn = get_conn()
    try:
        conn.execute("INSERT INTO holidays(name,date,year) VALUES(?,?,?)", (name,dt,year))
        conn.commit()
        flash(f"Holiday '{name}' added.", "success")
    except Exception:
        flash("Date already exists.", "error")
    conn.close()
    return redirect(url_for("holidays.index", year=year))

@holidays_bp.route("/delete/<int:hid>", methods=["POST"])
@login_required
def delete(hid):
    if current_user.role not in ("admin","hr"):
        flash("Not authorised.", "error")
        return redirect(url_for("holidays.index"))
    conn = get_conn()
    conn.execute("DELETE FROM holidays WHERE id=?", (hid,))
    conn.commit(); conn.close()
    flash("Holiday removed.", "info")
    return redirect(url_for("holidays.index"))
