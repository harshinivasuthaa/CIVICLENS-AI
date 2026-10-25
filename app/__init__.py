import os
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, redirect, url_for, session
from flask_wtf.csrf import CSRFProtect
from app.models import db, User, Complaint, Department, Category, SystemConfig
from app.services.security.auth_service import get_current_user

csrf = CSRFProtect()


def create_app(config_name: str = "development") -> Flask:
    """Application factory for CIVICLENS AI."""
    app = Flask(__name__)
    
    # Load configuration
    from config import config_by_name
    app.config.from_object(config_by_name.get(config_name, config_by_name["development"]))

    # Ensure required runtime directories exist
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)

    # Register Jinja2 template filters and global context
    @app.context_processor
    def inject_globals():
        user = get_current_user()
        unread_alerts = 0
        if user and user.is_officer():
            # count high delay or overdue active complaints
            unread_alerts = Complaint.query.filter(
                Complaint.status.in_(["SUBMITTED", "UNDER_REVIEW", "ASSIGNED"]),
                (Complaint.delay_risk_score >= 0.70) | (Complaint.priority_score >= 0.70)
            ).count()
        return {
            "current_user": user,
            "current_year": datetime.now(timezone.utc).year,
            "unread_alerts_count": unread_alerts,
        }

    @app.template_filter("status_badge")
    def status_badge_filter(status: str) -> str:
        mapping = {
            "SUBMITTED": "bg-primary",
            "UNDER_REVIEW": "bg-warning text-dark",
            "ASSIGNED": "bg-info text-dark",
            "IN_PROGRESS": "bg-purple text-white",
            "RESOLVED": "bg-success",
            "CLOSED": "bg-secondary",
            "REJECTED": "bg-danger",
            "REOPENED": "bg-orange text-white",
        }
        return mapping.get(status, "bg-secondary")

    @app.template_filter("priority_badge")
    def priority_badge_filter(priority: str) -> str:
        mapping = {
            "Urgent Review": "bg-danger",
            "Elevated Attention": "bg-warning text-dark",
            "Routine Review": "bg-success",
        }
        return mapping.get(priority, "bg-secondary")

    @app.template_filter("format_date")
    def format_date_filter(dt) -> str:
        if not dt:
            return "N/A"
        if isinstance(dt, str):
            return dt[:16]
        return dt.strftime("%b %d, %Y %H:%M")

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.citizen import citizen_bp
    from app.routes.officer import officer_bp
    from app.routes.admin import admin_bp
    from app.routes.analytics import analytics_bp
    from app.routes.ai_api import ai_api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(citizen_bp, url_prefix="/citizen")
    app.register_blueprint(officer_bp, url_prefix="/officer")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(analytics_bp, url_prefix="/analytics")
    app.register_blueprint(ai_api_bp, url_prefix="/api/ai")

    # Root route
    @app.route("/")
    def index():
        if "user_id" in session:
            role = session.get("role")
            if role == "citizen":
                return redirect(url_for("citizen.dashboard"))
            elif role in ("officer", "admin"):
                return redirect(url_for("officer.queue"))
        return redirect(url_for("analytics.public_dashboard"))

    # Health check probe
    @app.route("/health")
    def health_check():
        db_status = "connected"
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
        return jsonify({
            "status": "UP",
            "database": db_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
        }), 200

    # Custom Error Pages
    @app.errorhandler(400)
    def bad_request_error(e):
        return render_template("errors/400.html", error=e), 400

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template("errors/403.html", error=e), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template("errors/404.html", error=e), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    return app
