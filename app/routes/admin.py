import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from app.models import User, Department, Category, BatchImport, AuditLog, SystemConfig, Complaint, db
from app.services.security import roles_accepted, log_audit_event
from app.services.data_engineering import import_complaint_csv, generate_data_quality_report

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/users", methods=["GET", "POST"])
@roles_accepted("admin")
def manage_users():
    departments = Department.query.filter_by(is_active=True).all()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password")
        role = request.form.get("role", "officer")
        dept_id = request.form.get("department_id")

        if not username or not email or not password:
            flash("All fields are required.", "warning")
        elif User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already in use.", "warning")
        else:
            user = User(
                username=username,
                email=email,
                role=role,
                department_id=int(dept_id) if dept_id else None,
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            log_audit_event("USER_CREATED_BY_ADMIN", "user", user.id, {"username": username, "role": role})
            flash(f"User account '{username}' created successfully.", "success")
            return redirect(url_for("admin.manage_users"))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users, departments=departments)


@admin_bp.route("/import", methods=["GET", "POST"])
@roles_accepted("admin")
def batch_import():
    if request.method == "POST":
        if "csv_file" not in request.files:
            flash("No file part provided in request.", "warning")
            return redirect(url_for("admin.batch_import"))

        file = request.files["csv_file"]
        if not file or not file.filename:
            flash("No file selected.", "warning")
            return redirect(url_for("admin.batch_import"))

        if not file.filename.lower().endswith(".csv"):
            flash("Only .csv files are supported for municipal batch imports.", "danger")
            return redirect(url_for("admin.batch_import"))

        source_label = request.form.get("source_label", "MUNICIPAL_CSV")
        result = import_complaint_csv(file.stream, filename=file.filename, source=source_label)

        if result.get("success"):
            log_audit_event("CSV_BATCH_IMPORTED", "batch_import", result["batch_id"], {
                "accepted": result["accepted_rows"],
                "rejected": result["rejected_rows"],
            })
            flash(
                f"Import complete! {result['accepted_rows']} accepted, {result['rejected_rows']} rejected out of {result['total_rows']} rows.",
                "success" if result["rejected_rows"] == 0 else "warning",
            )
        else:
            flash(f"Import failed: {result.get('error')}", "danger")

        return redirect(url_for("admin.batch_import"))

    batches = BatchImport.query.order_by(BatchImport.imported_at.desc()).all()
    return render_template("admin/import.html", batches=batches)


@admin_bp.route("/data-quality")
@roles_accepted("admin")
def data_quality():
    report = generate_data_quality_report()
    return render_template("admin/quality.html", report=report)


@admin_bp.route("/audit-logs")
@roles_accepted("admin")
def audit_logs():
    action_filter = request.args.get("action")
    query = AuditLog.query
    if action_filter:
        query = query.filter_by(action=action_filter)
    logs = query.order_by(AuditLog.timestamp.desc()).limit(200).all()

    distinct_actions = [r[0] for r in db.session.query(AuditLog.action).distinct().all()]
    return render_template("admin/audit_logs.html", logs=logs, actions=distinct_actions, selected_action=action_filter)


@admin_bp.route("/config", methods=["GET", "POST"])
@roles_accepted("admin")
def system_config():
    if request.method == "POST":
        w_sev = float(request.form.get("w_sev", 0.30))
        w_time = float(request.form.get("w_time", 0.25))
        w_breach = float(request.form.get("w_breach", 0.20))
        w_rec = float(request.form.get("w_rec", 0.15))
        w_delay = float(request.form.get("w_delay", 0.10))

        total_weight = w_sev + w_time + w_breach + w_rec + w_delay
        if not (0.99 <= total_weight <= 1.01):
            flash(f"Priority weights must sum to 1.0 (Current sum: {total_weight:.2f})", "danger")
            return redirect(url_for("admin.system_config"))

        new_weights = {
            "severity": w_sev,
            "elapsed_time": w_time,
            "sla_breach": w_breach,
            "recurrence": w_rec,
            "delay_risk": w_delay,
        }

        cfg = SystemConfig.query.filter_by(key="priority_weights").first()
        if not cfg:
            cfg = SystemConfig(key="priority_weights", value=json.dumps(new_weights), description="Multi-factor weights")
            db.session.add(cfg)
        else:
            cfg.value = json.dumps(new_weights)
            cfg.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        log_audit_event("CONFIG_UPDATED", "system_config", "priority_weights", new_weights)
        flash("Priority formula weights successfully updated and saved.", "success")
        return redirect(url_for("admin.system_config"))

    cfg = SystemConfig.query.filter_by(key="priority_weights").first()
    current_weights = json.loads(cfg.value) if cfg else {
        "severity": 0.30, "elapsed_time": 0.25, "sla_breach": 0.20, "recurrence": 0.15, "delay_risk": 0.10
    }
    return render_template("admin/config.html", weights=current_weights)
