import sqlite3
import os
import bcrypt

# DB path: use env var (Docker) or fall back to local
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.environ.get("ERP_DB_PATH",
           os.path.join(BASE_DIR, "..", "erp.db"))

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL,
        full_name   TEXT NOT NULL,
        role        TEXT NOT NULL DEFAULT 'user',
        active      INTEGER DEFAULT 1,
        employee_id INTEGER UNIQUE REFERENCES employees(id)
    );

    CREATE TABLE IF NOT EXISTS role_permissions (
        role    TEXT NOT NULL,
        module  TEXT NOT NULL,
        allowed INTEGER DEFAULT 1,
        PRIMARY KEY (role, module)
    );

    CREATE TABLE IF NOT EXISTS employees (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name     TEXT NOT NULL,
        dept     TEXT NOT NULL,
        role     TEXT NOT NULL,
        join_date TEXT NOT NULL,
        salary   REAL NOT NULL,
        pan      TEXT UNIQUE NOT NULL,
        pf       INTEGER DEFAULT 1,
        esi      INTEGER DEFAULT 0,
        status   TEXT DEFAULT 'active'
    );

    CREATE TABLE IF NOT EXISTS projects (
        id       TEXT PRIMARY KEY,
        name     TEXT NOT NULL,
        client   TEXT NOT NULL,
        type     TEXT,
        status   TEXT DEFAULT 'active',
        start_date TEXT,
        end_date   TEXT,
        budget   REAL,
        spent    REAL DEFAULT 0,
        lead     TEXT,
        billing_type TEXT DEFAULT 'Fixed price'
    );

    CREATE TABLE IF NOT EXISTS project_members (
        project_id  TEXT,
        employee_id INTEGER,
        FOREIGN KEY(project_id)  REFERENCES projects(id),
        FOREIGN KEY(employee_id) REFERENCES employees(id)
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id  TEXT NOT NULL,
        title       TEXT NOT NULL,
        assigned_to INTEGER,
        due_date    TEXT,
        status      TEXT DEFAULT 'open',
        FOREIGN KEY(project_id)  REFERENCES projects(id),
        FOREIGN KEY(assigned_to) REFERENCES employees(id)
    );

    CREATE TABLE IF NOT EXISTS holidays (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT NOT NULL,
        date    TEXT UNIQUE NOT NULL,
        year    INTEGER
    );

    CREATE TABLE IF NOT EXISTS payslip_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        year        INTEGER,
        month       INTEGER,
        gross       REAL,
        net         REAL,
        generated_on TEXT DEFAULT (date('now')),
        generated_by TEXT,
        UNIQUE(employee_id, year, month),
        FOREIGN KEY(employee_id) REFERENCES employees(id)
    );

    CREATE TABLE IF NOT EXISTS milestones (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT,
        name       TEXT,
        due_date   TEXT,
        done       INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS timesheets (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        project_id  TEXT,
        task_id     INTEGER,
        work_date   TEXT,
        hours       REAL,
        notes       TEXT,
        status      TEXT DEFAULT 'draft',
        FOREIGN KEY(employee_id) REFERENCES employees(id),
        FOREIGN KEY(project_id)  REFERENCES projects(id),
        FOREIGN KEY(task_id)     REFERENCES tasks(id)
    );

    CREATE TABLE IF NOT EXISTS attendance (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        punch_date  TEXT,
        punch_in    TEXT,
        punch_out   TEXT,
        source      TEXT DEFAULT 'manual',
        FOREIGN KEY(employee_id) REFERENCES employees(id)
    );

    CREATE TABLE IF NOT EXISTS leave_types (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT UNIQUE NOT NULL,
        days    INTEGER NOT NULL,
        paid    INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS leave_balances (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        leave_type_id INTEGER,
        year        INTEGER,
        allocated   REAL DEFAULT 0,
        used        REAL DEFAULT 0,
        UNIQUE(employee_id, leave_type_id, year),
        FOREIGN KEY(employee_id)    REFERENCES employees(id),
        FOREIGN KEY(leave_type_id)  REFERENCES leave_types(id)
    );

    CREATE TABLE IF NOT EXISTS leave_requests (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        leave_type_id INTEGER,
        from_date   TEXT NOT NULL,
        to_date     TEXT NOT NULL,
        days        REAL NOT NULL,
        reason      TEXT,
        status      TEXT DEFAULT 'pending',
        applied_on  TEXT DEFAULT (date('now')),
        reviewed_by TEXT,
        reviewed_on TEXT,
        remarks     TEXT,
        FOREIGN KEY(employee_id)   REFERENCES employees(id),
        FOREIGN KEY(leave_type_id) REFERENCES leave_types(id)
    );

    CREATE TABLE IF NOT EXISTS smtp_config (
        id       INTEGER PRIMARY KEY CHECK (id=1),
        sender   TEXT,
        password TEXT,
        host     TEXT DEFAULT 'smtp.office365.com',
        port     INTEGER DEFAULT 587
    );

    CREATE TABLE IF NOT EXISTS config (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    conn.commit()

    # Seed demo employees if empty
    if c.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
        c.executemany("""
            INSERT INTO employees(name,dept,role,join_date,salary,pan,pf,esi,status)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, [
            ("Ravi Sharma",    "Engineering", "Senior Engineer",  "2021-03-15", 85000, "ABCDE1234F", 1, 0, "active"),
            ("Priya Nair",     "Engineering", "Engineer",         "2022-07-01", 65000, "FGHIJ5678K", 1, 0, "active"),
            ("Amit Joshi",     "Projects",    "Project Manager",  "2020-01-10", 95000, "KLMNO9012P", 1, 0, "active"),
            ("Sneha Patil",    "HR",          "HR Executive",     "2023-04-01", 45000, "QRSTU3456V", 1, 1, "active"),
            ("Mohammed Khan",  "Accounts",    "Accountant",       "2021-11-20", 55000, "WXYZA7890B", 1, 1, "active"),
            ("Deepa Reddy",    "Engineering", "Engineer",         "2022-09-15", 62000, "CDEFG2345H", 1, 0, "active"),
            ("Suresh Kumar",   "Projects",    "Site Engineer",    "2019-06-01", 58000, "HIJKL6789M", 1, 1, "on-leave"),
            ("Anjali Shah",    "Admin",       "Office Manager",   "2022-02-14", 42000, "NOPQR0123S", 1, 1, "active"),
        ])
        conn.commit()

    # Seed default users if empty
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        defaults = [
            ("admin", "admin123", "Administrator", "admin"),
            ("hr",    "hr123",    "HR Manager",    "hr"),
        ]
        for username, password, full_name, role in defaults:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            c.execute(
                "INSERT INTO users(username,password,full_name,role) VALUES(?,?,?,?)",
                (username, hashed.decode(), full_name, role)
            )
        conn.commit()

    # Seed default role permissions if empty
    if c.execute("SELECT COUNT(*) FROM role_permissions").fetchone()[0] == 0:
        # modules: timesheet, projects, leave
        # admin and hr get everything; user gets timesheet+leave only by default
        perms = []
        for mod in ["timesheet", "projects", "leave", "tasks"]:
            perms.append(("admin", mod, 1))
            perms.append(("hr",    mod, 1))
        perms.append(("user", "timesheet", 1))
        perms.append(("user", "projects",  0))
        perms.append(("user", "leave",     1))
        perms.append(("user", "tasks",     1))
        c.executemany(
            "INSERT OR IGNORE INTO role_permissions(role,module,allowed) VALUES(?,?,?)", perms
        )
        conn.commit()

    # Seed default leave types
    if c.execute("SELECT COUNT(*) FROM leave_types").fetchone()[0] == 0:
        c.executemany("INSERT INTO leave_types(name,days,paid) VALUES(?,?,?)", [
            ("Casual Leave",   12, 1),
            ("Sick Leave",     12, 1),
            ("Earned Leave",   15, 1),
            ("Maternity Leave",180, 1),
            ("Leave Without Pay", 0, 0),
        ])
        conn.commit()
        # Allocate balances for all existing employees for current year
        from datetime import date as _date
        year = _date.today().year
        emps  = c.execute("SELECT id FROM employees").fetchall()
        types = c.execute("SELECT id, days FROM leave_types WHERE paid=1").fetchall()
        for emp in emps:
            for lt in types:
                c.execute("""
                    INSERT OR IGNORE INTO leave_balances(employee_id,leave_type_id,year,allocated,used)
                    VALUES(?,?,?,?,0)
                """, (emp["id"], lt["id"], year, lt["days"]))
        conn.commit()

    # Seed default ESSL device address if not already set
    if c.execute("SELECT COUNT(*) FROM config WHERE key='essl_device'").fetchone()[0] == 0:
        c.execute("INSERT INTO config(key, value) VALUES('essl_device', '192.168.1.7:4320')")
        conn.commit()

    conn.close()
