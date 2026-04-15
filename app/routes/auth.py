from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint,
    abort,
    current_app,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
)
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app import db, bcrypt
from app.models import User

auth_bp = Blueprint("auth", __name__)


def _is_safe_redirect_target(target):
    if not target:
        return False

    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in ("http", "https") and host_url.netloc == redirect_url.netloc


def _normalize_email(value):
    return (value or "").strip().lower()


def _public_signup_enabled():
    return bool(current_app.config.get("PUBLIC_SIGNUP_ENABLED", True))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        data = request.form
        email = _normalize_email(data.get("email"))
        password = data.get("password") or ""

        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("auth/login.html")

        try:
            user = User.query.filter(func.lower(User.email) == email).first()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Login query failed for %s", email)
            flash("Login is temporarily unavailable. Please try again shortly.", "danger")
            return render_template("auth/login.html"), 503

        password_ok = False
        if user:
            try:
                password_ok = bool(bcrypt.check_password_hash(user.password, password))
            except (TypeError, ValueError):
                current_app.logger.warning("Invalid password hash for user id=%s", user.id)

        if user and password_ok and user.is_active:
            login_user(user, remember=data.get("remember") == "on")
            next_page = request.args.get("next", "")
            if _is_safe_redirect_target(next_page):
                return redirect(next_page)
            return redirect(url_for("dashboard.index"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if not _public_signup_enabled():
        abort(404)

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        data = request.form
        name = (data.get("name") or "").strip()
        email = _normalize_email(data.get("email"))
        password = data.get("password") or ""
        confirm_password = data.get("confirm_password") or ""

        if not name or not email or not password:
            flash("Name, email, and password are required.", "danger")
            return render_template("auth/signup.html"), 400

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/signup.html"), 400

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/signup.html"), 400

        try:
            existing = User.query.filter(func.lower(User.email) == email).first()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Signup lookup failed for %s", email)
            flash("Signup is temporarily unavailable. Please try again shortly.", "danger")
            return render_template("auth/signup.html"), 503

        if existing:
            flash("An account with this email already exists.", "danger")
            return render_template("auth/signup.html"), 409

        hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(email=email, password=hashed_pw, name=name, role="staff")

        try:
            db.session.add(user)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Signup create failed for %s", email)
            flash("Signup failed due to a server error. Please try again.", "danger")
            return render_template("auth/signup.html"), 503

        login_user(user)
        flash("Account created. Welcome!", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/signup.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
@login_required   # only existing admins can create new users
def register():
    if current_user.role != "admin":
        return jsonify({"error": "Forbidden"}), 403

    if request.method == "POST":
        data = request.form
        email = _normalize_email(data.get("email"))
        password = data.get("password") or ""
        name = (data.get("name") or "").strip()

        if not email or not password or not name:
            flash("Name, email, and password are required.", "danger")
            return render_template("auth/register.html"), 400

        try:
            existing = User.query.filter(func.lower(User.email) == email).first()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Admin register lookup failed for %s", email)
            flash("User creation is temporarily unavailable.", "danger")
            return render_template("auth/register.html"), 503

        if existing:
            flash("An account with this email already exists.", "danger")
            return render_template("auth/register.html"), 409

        hashed_pw = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
        user = User(
            email=email,
            password=hashed_pw,
            name=name,
            role="staff",
        )
        try:
            db.session.add(user)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Admin register create failed for %s", email)
            flash("User creation failed due to a server error.", "danger")
            return render_template("auth/register.html"), 503

        flash(f"User {user.email} created.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/register.html")