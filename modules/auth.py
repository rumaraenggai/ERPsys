import bcrypt
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)
from flask_login import (
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from .db import get_conn

auth_bp = Blueprint("auth", __name__)


# ── User model ──────────────────────────────────────────────


class User(UserMixin):
    def __init__(self, row):
        self.id = str(row["id"])
        self.username = row["username"]
        self.full_name = row["full_name"]
        self.role = row["role"]  # admin | hr | user
        self.active = bool(row["active"])
        self.employee_id = row["employee_id"] if row["employee_id"] else None

        # Added for forced password change flow.
        # Uses row.keys() so older DB rows do not cause drama, because naturally they would.
        self.must_change_password = (
            bool(row["must_change_password"])
            if "must_change_password" in row.keys()
            else False
        )

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
        row = conn.execute(
            "SELECT allowed FROM role_permissions WHERE role=? AND module=?",
            (self.role, module),
        ).fetchone()
        conn.close()

        return bool(row["allowed"]) if row else False


# Called by login_manager.user_loader
def load_user(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    conn.close()

    return User(row) if row and row["active"] else None


# ── Role guard decorator ─────────────────────────────────────


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


# ── Force password change guard ──────────────────────────────


@auth_bp.before_app_request
def force_password_change():
    if not current_user.is_authenticated:
        return

    allowed_endpoints = {
        "auth.change_password",
        "auth.logout",
        "static",
    }

    if current_user.must_change_password and request.endpoint not in allowed_endpoints:
        return redirect(url_for("auth.change_password"))


# ── Routes ──────────────────────────────────────────────────


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND active=1",
            (username,),
        ).fetchone()
        conn.close()

        if row and bcrypt.checkpw(password.encode(), row["password"].encode()):
            user = User(row)
            login_user(user, remember=bool(request.form.get("remember")))

            if user.must_change_password:
                return redirect(url_for("auth.change_password"))

            return redirect(request.args.get("next") or url_for("hr.index"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(new_password) < 4:
            flash("New password must be at least 4 characters.", "error")
            return redirect(url_for("auth.change_password"))

        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return redirect(url_for("auth.change_password"))

        conn = get_conn()

        row = conn.execute(
            "SELECT password FROM users WHERE id=?",
            (current_user.id,),
        ).fetchone()

        if not row or not bcrypt.checkpw(
            current_password.encode(),
            row["password"].encode(),
        ):
            conn.close()
            flash("Current password is incorrect.", "error")
            return redirect(url_for("auth.change_password"))

        hashed = bcrypt.hashpw(
            new_password.encode(),
            bcrypt.gensalt(),
        ).decode()

        conn.execute(
            """
            UPDATE users
            SET password=?,
                must_change_password=0,
                temp_password=NULL
            WHERE id=?
        """,
            (
                hashed,
                current_user.id,
            ),
        )

        conn.commit()
        conn.close()

        flash("Password changed successfully.", "success")
        return redirect(url_for("hr.index"))

    return render_template("change_password.html")


# ── User management admin only ───────────────────────────────


@auth_bp.route("/users")
@roles_required("admin")
def users():
    conn = get_conn()

    users = conn.execute("""
        SELECT
            id,
            username,
            full_name,
            role,
            active,
            employee_id,
            must_change_password
        FROM users
    """).fetchall()

    perms = conn.execute("""
        SELECT *
        FROM role_permissions
        ORDER BY role, module
    """).fetchall()

    conn.close()

    modules = ["timesheet", "projects", "leave", "tasks"]
    roles = ["hr", "user"]

    # Build dict: {role: {module: allowed}}
    perm_map = {r: {m: 0 for m in modules} for r in roles}

    for p in perms:
        if p["role"] in perm_map:
            perm_map[p["role"]][p["module"]] = p["allowed"]

    return render_template(
        "users.html",
        users=users,
        perm_map=perm_map,
        modules=modules,
        roles=roles,
    )


@auth_bp.route("/users/add", methods=["POST"])
@roles_required("admin")
def add_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    full_name = request.form.get("full_name", "").strip()
    role = request.form.get("role", "user")

    if role not in ("admin", "hr", "user"):
        role = "user"

    if not all([username, password, full_name]):
        flash("All fields are required.", "error")
        return redirect(url_for("auth.users"))

    hashed = bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt(),
    ).decode()

    try:
        conn = get_conn()

        conn.execute(
            """
            INSERT INTO users(
                username,
                password,
                full_name,
                role,
                must_change_password,
                temp_password
            )
            VALUES (?, ?, ?, ?, 1, ?)
        """,
            (
                username,
                hashed,
                full_name,
                role,
                password,
            ),
        )

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

    conn.execute(
        "UPDATE users SET active = 1 - active WHERE id=?",
        (uid,),
    )

    conn.commit()
    conn.close()

    flash("User status updated.", "info")
    return redirect(url_for("auth.users"))


@auth_bp.route("/users/role/<int:uid>", methods=["POST"])
@roles_required("admin")
def change_role(uid):
    new_role = request.form.get("role", "user")

    if new_role not in ("admin", "hr", "user"):
        flash("Invalid role.", "error")
        return redirect(url_for("auth.users"))

    conn = get_conn()

    conn.execute(
        "UPDATE users SET role=? WHERE id=?",
        (new_role, uid),
    )

    conn.commit()
    conn.close()

    flash("Role updated.", "success")
    return redirect(url_for("auth.users"))


@auth_bp.route("/users/reset-password/<int:uid>", methods=["POST"])
@roles_required("admin")
def reset_password(uid):
    conn = get_conn()

    user = conn.execute(
        "SELECT username FROM users WHERE id=?",
        (uid,),
    ).fetchone()

    if not user:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for("auth.users"))

    # Reset password to username.
    # Yes, this is intentionally simple because that is the chosen workflow.
    raw_pw = user["username"]

    hashed = bcrypt.hashpw(
        raw_pw.encode(),
        bcrypt.gensalt(),
    ).decode()

    conn.execute(
        """
        UPDATE users
        SET password=?,
            must_change_password=1,
            temp_password=?
        WHERE id=?
    """,
        (
            hashed,
            raw_pw,
            uid,
        ),
    )

    conn.commit()
    conn.close()

    flash(
        f"Password reset. Temporary password is same as username: {raw_pw}",
        "success",
    )

    return redirect(url_for("auth.users"))


@auth_bp.route("/users/permissions", methods=["POST"])
@roles_required("admin")
def save_permissions():
    modules = ["timesheet", "projects", "leave", "tasks"]
    roles = ["hr", "user"]

    conn = get_conn()

    for role in roles:
        for module in modules:
            allowed = 1 if request.form.get(f"{role}_{module}") else 0

            conn.execute(
                """
                INSERT INTO role_permissions(role, module, allowed)
                VALUES (?, ?, ?)
                ON CONFLICT(role, module)
                DO UPDATE SET allowed=excluded.allowed
            """,
                (
                    role,
                    module,
                    allowed,
                ),
            )

    conn.commit()
    conn.close()

    flash("Permissions updated.", "success")
    return redirect(url_for("auth.users"))


# ── Admin credentials page ───────────────────────────────────


@auth_bp.route("/users/credentials")
@roles_required("admin")
def credentials():
    conn = get_conn()

    users = conn.execute("""
        SELECT
            id,
            username,
            full_name,
            role,
            active,
            employee_id,
            must_change_password,
            CASE
                WHEN temp_password IS NOT NULL THEN 1
                ELSE 0
            END AS has_temp_password
        FROM users
        ORDER BY role, full_name
    """).fetchall()

    conn.close()

    return render_template("credentials.html", users=users)


@auth_bp.route("/users/credentials/reveal/<int:uid>", methods=["POST"])
@roles_required("admin")
def reveal_credential(uid):
    admin_password = request.form.get("admin_password", "")

    conn = get_conn()

    admin = conn.execute(
        "SELECT password FROM users WHERE id=? AND active=1",
        (current_user.id,),
    ).fetchone()

    if not admin or not bcrypt.checkpw(
        admin_password.encode(),
        admin["password"].encode(),
    ):
        conn.close()
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Admin password is incorrect.",
                }
            ),
            403,
        )

    user = conn.execute(
        "SELECT temp_password FROM users WHERE id=?",
        (uid,),
    ).fetchone()

    conn.close()

    if not user or not user["temp_password"]:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "No temporary password available. The user has probably changed it already.",
                }
            ),
            404,
        )

    return jsonify(
        {
            "ok": True,
            "password": user["temp_password"],
        }
    )
