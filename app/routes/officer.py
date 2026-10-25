import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from app.models import Complaint, Category, Department, User, ComplaintStatusHistory, ComplaintComment, DuplicateSuggestion, AIPredictionRecord, db
from app.services.security import roles_accepted, log_audit_event
from app.services.ai import calculate_priority_score, update_complaint_priority

officer_bp = Blueprint("officer", __name__)


@officer_bp.route("/queue")
@roles_accepted("officer", "admin")
def queue():
    dept_filter = request.args.get("dept")
    cat_filter = request.args.get("cat")
    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")
    sort_by = request.args.get("sort", "priority")  # priority or date

    query = Complaint.query

    # Officers restricted to their assigned department unless unassigned or Admin
    current_dept_id = session.get("department_id")
    current_role = session.get("role")
    if current_role == "officer" and current_dept_id:
        query = query.filter_by(dept_id=current_dept_id)
    elif dept_filter:
        query = query.filter_by(dept_id=dept_filter)

    if cat_filter:
        query = query.filter_by(category_id=cat_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(final_priority=priority_filter)

    if sort_by == "priority":
        query = query.order_by(Complaint.priority_score.desc(), Complaint.submitted_at.desc())
    else:
        query = query.order_by(Complaint.submitted_at.desc())

    complaints = query.limit(100).all()

    departments = Department.query.filter_by(is_active=True).all()
    categories = Category.query.all()

    return render_template(
        "officer/queue.html",
        complaints=complaints,
        departments=departments,
        categories=categories,
        selected_dept=dept_filter,
        selected_cat=cat_filter,
        selected_status=status_filter,
        selected_priority=priority_filter,
        selected_sort=sort_by,
    )


@officer_bp.route("/complaint/<reference_no>")
@roles_accepted("officer", "admin")
def review_detail(reference_no):
    complaint = Complaint.query.filter_by(reference_no=reference_no).first_or_404()
    
    # Priority Breakdown json parse
    breakdown = {}
    if complaint.priority_breakdown:
        try:
            breakdown = json.loads(complaint.priority_breakdown)
        except Exception:
            pass

    # Delay factors json parse
    delay_factors = {}
    if complaint.delay_risk_factors:
        try:
            delay_factors = json.loads(complaint.delay_risk_factors)
        except Exception:
            pass

    departments = Department.query.filter_by(is_active=True).all()
    categories = Category.query.all()
    officers = User.query.filter(User.role.in_(["officer", "admin"])).all()
    duplicates = DuplicateSuggestion.query.filter_by(complaint_id=complaint.id).all()

    return render_template(
        "officer/review_detail.html",
        complaint=complaint,
        breakdown=breakdown,
        delay_factors=delay_factors,
        departments=departments,
        categories=categories,
        officers=officers,
        duplicates=duplicates,
    )


@officer_bp.route("/complaint/<reference_no>/status", methods=["POST"])
@roles_accepted("officer", "admin")
def update_status(reference_no):
    complaint = Complaint.query.filter_by(reference_no=reference_no).first_or_404()
    new_status = request.form.get("status")
    assigned_officer_id = request.form.get("assigned_officer_id")
    resolution_notes = request.form.get("resolution_notes", "").strip()
    rejection_reason = request.form.get("rejection_reason", "").strip()
    internal_comment = request.form.get("internal_comment", "").strip()
    user_id = session.get("user_id")

    valid_statuses = {"SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED", "REJECTED", "REOPENED"}
    if new_status not in valid_statuses:
        flash("Invalid status transition requested.", "danger")
        return redirect(url_for("officer.review_detail", reference_no=reference_no))

    # Strict Validation: Resolved status requires resolution note
    if new_status in ("RESOLVED", "CLOSED") and not resolution_notes:
        flash("Resolution notes are strictly required before marking a complaint as resolved or closed.", "warning")
        return redirect(url_for("officer.review_detail", reference_no=reference_no))

    # Strict Validation: Rejected status requires documented rejection reason
    if new_status == "REJECTED" and not rejection_reason:
        flash("A mandatory rejection reason must be documented.", "warning")
        return redirect(url_for("officer.review_detail", reference_no=reference_no))

    old_status = complaint.status
    complaint.status = new_status

    if assigned_officer_id:
        complaint.assigned_officer_id = int(assigned_officer_id)
        if not complaint.assigned_at:
            complaint.assigned_at = datetime.now(timezone.utc)

    now_utc = datetime.now(timezone.utc)
    if new_status in ("RESOLVED", "CLOSED"):
        complaint.resolved_at = now_utc
        complaint.resolution_notes = resolution_notes
    elif new_status == "REJECTED":
        complaint.rejection_reason = rejection_reason

    # Append status history audit
    history_note = f"Status changed from {old_status} to {new_status}."
    if resolution_notes:
        history_note += f" Resolution: {resolution_notes}"
    if rejection_reason:
        history_note += f" Rejection reason: {rejection_reason}"

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=old_status,
        new_status=new_status,
        changed_by_id=user_id,
        remarks=history_note,
    )
    db.session.add(history)

    # Add internal officer comment if provided
    if internal_comment:
        comm = ComplaintComment(
            complaint_id=complaint.id,
            author_id=user_id,
            comment=internal_comment,
            is_internal=True,
        )
        db.session.add(comm)

    db.session.commit()

    # Recalculate priority to update backlog impact
    update_complaint_priority(complaint)

    log_audit_event("STATUS_UPDATE", "complaint", reference_no, {
        "old_status": old_status,
        "new_status": new_status,
        "assigned_to": assigned_officer_id,
    })

    flash(f"Complaint updated to {new_status}.", "success")
    return redirect(url_for("officer.review_detail", reference_no=reference_no))


@officer_bp.route("/complaint/<reference_no>/override-priority", methods=["POST"])
@roles_accepted("officer", "admin")
def override_priority(reference_no):
    complaint = Complaint.query.filter_by(reference_no=reference_no).first_or_404()
    new_priority = request.form.get("priority")
    override_reason = request.form.get("reason", "").strip()
    user_id = session.get("user_id")

    if not override_reason:
        flash("A documented reason is mandatory when overriding the AI/calculated priority.", "warning")
        return redirect(url_for("officer.review_detail", reference_no=reference_no))

    old_priority = complaint.final_priority
    complaint.final_priority = new_priority
    complaint.priority_override_reason = override_reason

    # Add to status history for transparency
    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=complaint.status,
        new_status=complaint.status,
        changed_by_id=user_id,
        remarks=f"Priority adjusted from {old_priority} to {new_priority}. Justification: {override_reason}",
    )
    db.session.add(history)
    db.session.commit()

    log_audit_event("PRIORITY_OVERRIDE", "complaint", reference_no, {
        "old_priority": old_priority,
        "new_priority": new_priority,
        "reason": override_reason,
    })

    flash(f"Priority recommendation updated to '{new_priority}'. Audit recorded.", "info")
    return redirect(url_for("officer.review_detail", reference_no=reference_no))


@officer_bp.route("/complaint/<reference_no>/reclassify", methods=["POST"])
@roles_accepted("officer", "admin")
def reclassify_category(reference_no):
    complaint = Complaint.query.filter_by(reference_no=reference_no).first_or_404()
    new_cat_id = request.form.get("category_id")
    user_id = session.get("user_id")

    category = Category.query.get_or_404(new_cat_id)
    old_cat_name = complaint.category.name if complaint.category else "None"
    
    complaint.category_id = category.id
    complaint.dept_id = category.dept_id

    # Record AI correction feedback
    pred = AIPredictionRecord(
        complaint_id=complaint.id,
        prediction_type="category_correction_feedback",
        prediction_value=category.name,
        confidence=1.0,
        model_version="human_expert_correction",
        explanation_json=json.dumps({"corrected_from": old_cat_name, "corrected_by": user_id}),
    )
    db.session.add(pred)

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=complaint.status,
        new_status=complaint.status,
        changed_by_id=user_id,
        remarks=f"Reclassified category from '{old_cat_name}' to '{category.name}'. Department set to {category.department.dept_name}.",
    )
    db.session.add(history)
    db.session.commit()

    update_complaint_priority(complaint)
    log_audit_event("COMPLAINT_RECLASSIFIED", "complaint", reference_no, {"old_category": old_cat_name, "new_category": category.name})

    flash(f"Complaint category updated to '{category.name}'.", "success")
    return redirect(url_for("officer.review_detail", reference_no=reference_no))


@officer_bp.route("/complaint/<reference_no>/duplicate/<int:suggestion_id>", methods=["POST"])
@roles_accepted("officer", "admin")
def review_duplicate(reference_no, suggestion_id):
    suggestion = DuplicateSuggestion.query.get_or_404(suggestion_id)
    action = request.form.get("action")  # 'CONFIRM' or 'DISMISS'
    user_id = session.get("user_id")

    if action == "CONFIRM":
        suggestion.review_status = "CONFIRMED_DUPLICATE"
        flash("Duplicate association confirmed. Audit trail linked.", "info")
    else:
        suggestion.review_status = "DISMISSED"
        flash("Duplicate alert dismissed.", "secondary")

    suggestion.reviewed_by_id = user_id
    suggestion.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit_event("DUPLICATE_REVIEW", "duplicate_suggestion", suggestion_id, {"action": suggestion.review_status})
    return redirect(url_for("officer.review_detail", reference_no=reference_no))


@officer_bp.route("/alerts")
@roles_accepted("officer", "admin")
def alerts():
    """Operational alerts panel for backlogs, overdue SLA breaches, and high delay risks."""
    # 1. Overdue complaints
    all_active = Complaint.query.filter(
        Complaint.status.in_(["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"]),
        Complaint.deadline_at.isnot(None),
    ).all()
    overdue_complaints = [c for c in all_active if c.is_overdue()]

    # 2. High delay risk complaints
    high_delay = Complaint.query.filter(
        Complaint.status.in_(["SUBMITTED", "UNDER_REVIEW", "ASSIGNED"]),
        Complaint.delay_risk_score >= 0.70,
    ).all()

    # 3. Low-confidence classifications needing human triage
    low_confidence = Complaint.query.filter(
        Complaint.status == "SUBMITTED",
        Complaint.priority_score >= 0.70,
    ).limit(10).all()

    return render_template(
        "officer/alerts.html",
        overdue_complaints=overdue_complaints,
        high_delay=high_delay,
        low_confidence=low_confidence,
    )
