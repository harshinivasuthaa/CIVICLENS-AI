from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import User, db
from app.services.security import (
    login_user,
    logout_user,
    is_rate_limited,
    record_failed_attempt,
    reset_failed_attempts,
    log_audit_event,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        role = session.get("role")
        if role == "citizen":
            return redirect(url_for("citizen.dashboard"))
        return redirect(url_for("officer.queue"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip_addr = request.remote_addr

        if is_rate_limited(ip_addr) or is_rate_limited(username):
            flash("Too many failed attempts. Account temporarily locked for 5 minutes.", "danger")
            return render_template("auth/login.html")

        user = User.query.filter_by(username=username).first()
        if user and user.is_active and user.check_password(password):
            reset_failed_attempts(ip_addr)
            reset_failed_attempts(username)
            login_user(user)
            log_audit_event("USER_LOGIN", "user", user.id, {"username": user.username, "role": user.role})
            flash(f"Welcome back, {user.username}!", "success")

            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)

            if user.role == "citizen":
                return redirect(url_for("citizen.dashboard"))
            elif user.role in ("officer", "admin"):
                return redirect(url_for("officer.queue"))
            return redirect(url_for("analytics.public_dashboard"))
        else:
            record_failed_attempt(ip_addr)
            record_failed_attempt(username)
            log_audit_event("FAILED_LOGIN_ATTEMPT", "user", username, {"ip": ip_addr})
            flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "warning")
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "warning")
            return render_template("auth/register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "warning")
            return render_template("auth/register.html")

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already registered.", "warning")
            return render_template("auth/register.html")

        # Citizen self-registration always assigns role 'citizen' (prevents privilege escalation)
        user = User(username=username, email=email, role="citizen", is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        log_audit_event("USER_REGISTERED", "user", user.id, {"username": user.username, "role": "citizen"})
        flash("Registration successful. Please log in with your credentials.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    if user_id:
        log_audit_event("USER_LOGOUT", "user", user_id)
    logout_user()
    flash("You have been securely logged out.", "info")
    return redirect(url_for("auth.login"))
