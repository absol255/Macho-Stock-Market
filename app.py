from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Admin
import time
import click

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)

app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = "login"

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():

    if request.path.startswith("/api/"):

        return jsonify({
            "error": "Login required"
        }), 401

    return redirect(url_for("login"))

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json

    username = data.get("username")
    password = data.get("password")

    admin = Admin.query.filter_by(
        username=username
    ).first()

    if not admin:
        time.sleep(1)

        return jsonify({
            "error": "Invalid username"
        }), 401

    if not admin.check_password(password):

        time.sleep(1)

        return jsonify({
            "error": "Invalid password"
        }), 401

    login_user(admin)

    return jsonify({
        "success": True
    })

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html")

@app.route("/login")
def login():
    return render_template("login.html")