from urllib.parse import urljoin, urlparse

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required

from app import db, bcrypt
from app.models import User

auth_bp = Blueprint("auth", __name__)


def _is_safe_redirect_target(target):
    if not target:
        return False

    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in ("http", "https") and host_url.netloc == redirect_url.netloc


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.form
        user = User.query.filter_by(email=data.get("email")).first()
        if user and bcrypt.check_password_hash(user.password, data.get("password")):
            login_user(user, remember=data.get("remember") == "on")
            next_page = request.args.get("next", "")
            if _is_safe_redirect_target(next_page):
                return redirect(next_page)
            return redirect(url_for("dashboard.index"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
@login_required   # only existing admins can create new users
def register():
    from flask_login import current_user
    if current_user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403

    if request.method == "POST":
        data = request.form
        hashed_pw = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
        user = User(
            email=data["email"],
            password=hashed_pw,
            name=data.get("name"),
            role=data.get("role", "staff"),
        )
        db.session.add(user)
        db.session.commit()
        flash(f"User {user.email} created.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/register.html")