import json
from datetime import datetime, timezone, timedelta
import numpy as np
from flask import Blueprint, render_template, request, jsonify, session
from app.models import Complaint, Category, Department, db
from app.services.data_engineering.exporter import export_complaints_csv
from app.services.ai.delay_model import delay_service

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/public-dashboard")
def public_dashboard():
    """
    Public Transparency Portal.
    Displays aggregated metrics with zero disclosure of citizen PII or internal officer notes.
    """
    total = Complaint.query.count()
    resolved = Complaint.query.filter(Complaint.status.in_(["RESOLVED", "CLOSED"])).count()
    active = Complaint.query.filter(Complaint.status.in_(["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"])).count()
    reopened = Complaint.query.filter_by(status="REOPENED").count()

    # Median resolution time calculation for resolved complaints
    resolved_complaints = Complaint.query.filter(
        Complaint.status.in_(["RESOLVED", "CLOSED"]),
        Complaint.resolved_at.isnot(None),
        Complaint.submitted_at.isnot(None),
    ).all()

    resolution_durations = []
    for c in resolved_complaints:
        sub = c.submitted_at.replace(tzinfo=timezone.utc) if c.submitted_at.tzinfo is None else c.submitted_at
        res = c.resolved_at.replace(tzinfo=timezone.utc) if c.resolved_at.tzinfo is None else c.resolved_at
        duration_hrs = max(0.0, (res - sub).total_seconds() / 3600.0)
        resolution_durations.append(duration_hrs)

    median_res_hours = round(float(np.median(resolution_durations)), 1) if resolution_durations else 0.0
    avg_res_hours = round(float(np.mean(resolution_durations)), 1) if resolution_durations else 0.0

    # Category breakdown for Chart.js
    categories = Category.query.all()
    cat_labels = [c.name for c in categories]
    cat_counts = [Complaint.query.filter_by(category_id=c.id).count() for c in categories]

    # Locality aggregated summaries (no precise coordinates exposed publicly)
    localities = (
        db.session.query(Complaint.locality, db.func.count(Complaint.id).label("count"))
        .group_by(Complaint.locality)
        .order_by(db.desc("count"))
        .limit(10)
        .all()
    )

    return render_template(
        "analytics/public_dashboard.html",
        total=total,
        resolved=resolved,
        active=active,
        reopened=reopened,
        median_res_hours=median_res_hours,
        avg_res_hours=avg_res_hours,
        cat_labels=json.dumps(cat_labels),
        cat_counts=json.dumps(cat_counts),
        top_localities=localities,
    )


@analytics_bp.route("/hotspots")
def hotspots():
    """Geographic hotspot visualization using Leaflet with graceful offline fallback."""
    category_id = request.args.get("category_id")
    dept_id = request.args.get("dept_id")
    status = request.args.get("status")

    query = Complaint.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if dept_id:
        query = query.filter_by(dept_id=dept_id)
    if status:
        query = query.filter_by(status=status)

    # Fetch complaints that have coordinates
    geo_complaints = query.filter(
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None),
    ).limit(300).all()

    points = []
    for c in geo_complaints:
        points.append({
            "reference_no": c.reference_no,
            "title": c.title,
            "lat": c.latitude,
            "lng": c.longitude,
            "locality": c.locality,
            "category": c.category.name if c.category else "Unclassified",
            "status": c.status,
            "priority": c.final_priority,
            "priority_score": c.priority_score,
            "delay_risk": c.delay_risk_level,
        })

    # Summary by locality for table view fallback
    locality_clusters = (
        db.session.query(Complaint.locality, db.func.count(Complaint.id).label("total"))
        .group_by(Complaint.locality)
        .order_by(db.desc("total"))
        .limit(15)
        .all()
    )

    categories = Category.query.all()
    departments = Department.query.filter_by(is_active=True).all()

    return render_template(
        "analytics/hotspots.html",
        points_json=json.dumps(points),
        locality_clusters=locality_clusters,
        categories=categories,
        departments=departments,
        selected_cat=category_id,
        selected_dept=dept_id,
        selected_status=status,
    )


@analytics_bp.route("/delay-eval")
def delay_evaluation():
    """AI Model Evaluation dashboard comparing ML predictions vs operational baselines."""
    resolved_count = Complaint.query.filter(
        Complaint.status.in_(["RESOLVED", "CLOSED"]),
        Complaint.resolved_at.isnot(None),
        Complaint.deadline_at.isnot(None),
    ).count()

    is_ml_active = delay_service.is_loaded

    # Baseline comparison metrics
    eval_info = {
        "eligible_records": resolved_count,
        "is_model_trained": is_ml_active,
        "model_type": "Random Forest Supervised Classifier" if is_ml_active else "Deterministic Heuristic Operational Baseline",
        "training_threshold_min": 20,
        "features_evaluated": delay_service.feature_names,
    }

    return render_template("analytics/delay_eval.html", eval_info=eval_info)


@analytics_bp.route("/reports")
def reports():
    categories = Category.query.all()
    departments = Department.query.filter_by(is_active=True).all()
    return render_template("analytics/reports.html", categories=categories, departments=departments)


@analytics_bp.route("/export-csv")
def export_csv():
    category_id = request.args.get("category_id")
    dept_id = request.args.get("dept_id")
    status = request.args.get("status")

    query = Complaint.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if dept_id:
        query = query.filter_by(dept_id=dept_id)
    if status:
        query = query.filter_by(status=status)

    is_staff = session.get("role") in ("officer", "admin")
    return export_complaints_csv(query, include_pii=is_staff)
