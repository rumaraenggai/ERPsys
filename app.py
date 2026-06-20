import sys
import os
from flask import Flask
from flask_login import LoginManager
from modules.db import init_db
from modules.hr import hr_bp
from modules.projects import projects_bp
from modules.timesheet import timesheet_bp
from modules.salary import salary_bp
from modules.biometric import biometric_bp
from modules.leave import leave_bp
from modules.tasks import tasks_bp
from modules.dashboard import dashboard_bp
from modules.reports import reports_bp
from modules.holidays import holidays_bp
from modules.auth import auth_bp, load_user
import webbrowser

app = Flask(__name__)
from datetime import datetime
app.jinja_env.filters['datetimeformat'] = lambda v, f: datetime.strptime(v, '%Y-%m-%d').strftime(f)
app.secret_key = "erp-secret-key-change-in-prod"

# Document uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB limit

# Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "error"
login_manager.user_loader(load_user)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(hr_bp, url_prefix="/hr")
app.register_blueprint(projects_bp, url_prefix="/projects")
app.register_blueprint(timesheet_bp, url_prefix="/timesheet")
app.register_blueprint(salary_bp, url_prefix="/salary")
app.register_blueprint(biometric_bp, url_prefix="/biometric")
app.register_blueprint(leave_bp,      url_prefix="/leave")
app.register_blueprint(tasks_bp,      url_prefix="/tasks")
app.register_blueprint(dashboard_bp,  url_prefix="/dashboard")
app.register_blueprint(reports_bp,    url_prefix="/reports")
app.register_blueprint(holidays_bp,   url_prefix="/holidays")

@app.route("/")
def index():
    from flask import redirect
    return redirect("/dashboard")

def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)
