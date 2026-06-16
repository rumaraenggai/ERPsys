import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import UserMixin, login_user, logout_user, login_required
from .db import get_conn

auth_bp = Blueprint("auth", __name__)

# ── User model ──────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, row):
        self.id          = str(row["id"])
        self.username    = row["username"]
        self.full_name   = row["full_name"]
        self.role        = row["role"]       # admin | hr | user
        self.active      = bool(row["active"])
        self.employee_id = row["employee_id"] if row["employee_id"] else None

    def get_id(self):
        return self.id

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_hr(self):
        return self.role in ("admin", "hr")

    def can(self, module):
        """Check role_permissions for this role + module. Admin always True."""
        if self.role == "admin":
            return True
        conn = get_conn()
        row  = conn.execute(
            "SELECT allowed FROM role_permissions WHERE role=? AND module=?",
            (self.role, module)
        ).fetchone()
        conn.close()
        return bool(row["allowed"]) if row else False

# Called by login_manager.user_loader
def load_user(user_id):
    conn = get_conn()
    row  = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return User(row) if row and row["active"] else None

# ── Role guard decorator ─────────────────────────────────────
from functools import wraps
from flask_login import current_user

def roles_required(*roles):
    """Restrict a route to specific roles. Usage: @roles_required('admin','hr')"""
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                flash("You don't have permission to access that page.", "error")
                return redirect(url_for("hr.index"))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ── Routes ──────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_conn()
        row  = conn.execute("SELECT * FROM users WHERE username=? AND active=1",
                            (username,)).fetchone()
        conn.close()
        if row and bcrypt.checkpw(password.encode(), row["password"].encode()):
            login_user(User(row), remember=bool(request.form.get("remember")))
            return redirect(request.args.get("next") or url_for("hr.index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

# ── User management (admin only) ────────────────────────────
@auth_bp.route("/users")
@roles_required("admin")
def users():
    conn  = get_conn()
    users = conn.execute("SELECT id,username,full_name,role,active,employee_id FROM users").fetchall()
    perms = conn.execute("SELECT * FROM role_permissions ORDER BY role,module").fetchall()
    conn.close()
    modules = ["timesheet", "projects", "leave"]
    roles   = ["hr", "user"]
    # Build dict: {role: {module: allowed}}
    perm_map = {r: {m: 0 for m in modules} for r in roles}
    for p in perms:
        if p["role"] in perm_map:
            perm_map[p["role"]][p["module"]] = p["allowed"]
    return render_template("users.html", users=users,
                           perm_map=perm_map, modules=modules, roles=roles)

@auth_bp.route("/users/add", methods=["POST"])
@roles_required("admin")
def add_user():
    username  = request.form.get("username","").strip()
    password  = request.form.get("password","")
    full_name = request.form.get("full_name","").strip()
    role      = request.form.get("role","viewer")
    if not all([username, password, full_name]):
        flash("All fields are required.", "error")
        return redirect(url_for("auth.users"))
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        conn = get_conn()
        conn.execute("INSERT INTO users(username,password,full_name,role) VALUES(?,?,?,?)",
                     (username, hashed, full_name, role))
        conn.commit()
        conn.close()
        flash(f"User '{username}' created.", "success")
    except Exception:
        flash("Username already exists.", "error")
    return redirect(url_for("auth.users"))

@auth_bp.route("/users/toggle/<int:uid>", methods=["POST"])
@roles_required("admin")
def toggle_user(uid):
    conn = get_conn()
    conn.execute("UPDATE users SET active = 1 - active WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    flash("User status updated.", "info")
    return redirect(url_for("auth.users"))

@auth_bp.route("/users/role/<int:uid>", methods=["POST"])
@roles_required("admin")
def change_role(uid):
    new_role = request.form.get("role","viewer")
    if new_role not in ("admin","hr","viewer"):
        flash("Invalid role.", "error")
        return redirect(url_for("auth.users"))
    conn = get_conn()
    conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, uid))
    conn.commit()
    conn.close()
    flash("Role updated.", "success")
    return redirect(url_for("auth.users"))


@roles_required("admin")
def reset_password(uid):
    new_pw = request.form.get("new_password","")
    if len(new_pw) < 4:
        flash("Password must be at least 4 characters.", "error")
        return redirect(url_for("auth.users"))
    hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    conn = get_conn()
    conn.execute("UPDATE users SET password=? WHERE id=?", (hashed, uid))
    conn.commit()
    conn.close()
    flash("Password reset.", "success")
    return redirect(url_for("auth.users"))

@auth_bp.route("/users/permissions", methods=["POST"])
@roles_required("admin")
def save_permissions():
    modules = ["timesheet", "projects", "leave"]
    roles   = ["hr", "user"]
    conn    = get_conn()
    for role in roles:
        for module in modules:
            allowed = 1 if request.form.get(f"{role}_{module}") else 0
            conn.execute("""
                INSERT INTO role_permissions(role, module, allowed)
                VALUES(?,?,?)
                ON CONFLICT(role,module) DO UPDATE SET allowed=excluded.allowed
            """, (role, module, allowed))
    conn.commit()
    conn.close()
    flash("Permissions updated.", "success")
    return redirect(url_for("auth.users"))
