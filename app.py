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
from modules.auth import auth_bp, load_user

app = Flask(__name__)
app.secret_key = "erp-secret-key-change-in-prod"

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
app.register_blueprint(leave_bp, url_prefix="/leave")

@app.route("/")
def index():
    from flask import redirect
    return redirect("/hr")

def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)
