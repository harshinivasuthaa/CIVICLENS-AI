from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from app.models import Complaint, Category, Department, ComplaintStatusHistory, ComplaintComment, db
from app.services.security import login_required, citizen_owns_complaint, save_quarantined_upload, log_audit_event
from app.services.data_engineering import generate_reference_no
from app.services.ai import classifier_service, update_complaint_priority, record_duplicate_suggestions

citizen_bp = Blueprint("citizen", __name__)


@citizen_bp.route("/dashboard")
@login_required
def dashboard():
    user_id = session.get("user_id")
    my_complaints = Complaint.query.filter_by(citizen_id=user_id).order_by(Complaint.submitted_at.desc()).all()

    total = len(my_complaints)
    in_progress = sum(1 for c in my_complaints if c.status in ("SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"))
    resolved = sum(1 for c in my_complaints if c.status in ("RESOLVED", "CLOSED"))
    reopened = sum(1 for c in my_complaints if c.status == "REOPENED")

    return render_template(
        "citizen/dashboard.html",
        complaints=my_complaints[:10],
        total=total,
        in_progress=in_progress,
        resolved=resolved,
        reopened=reopened,
    )


@citizen_bp.route("/submit", methods=["GET", "POST"])
@login_required
def submit_complaint():
    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        locality = request.form.get("locality", "").strip()
        category_id = request.form.get("category_id")
        lat_str = request.form.get("latitude")
        lon_str = request.form.get("longitude")
        user_id = session.get("user_id")

        if not title or not description or not locality:
            flash("Title, description, and locality are required fields.", "warning")
            return render_template("citizen/submit.html", categories=categories)

        # Latitude & Longitude validation
        latitude, longitude = None, None
        if lat_str and lon_str:
            try:
                lat_val = float(lat_str)
                lon_val = float(lon_str)
                if -90.0 <= lat_val <= 90.0 and -180.0 <= lon_val <= 180.0:
                    latitude = lat_val
                    longitude = lon_val
            except ValueError:
                pass

        # Handle file attachment
        attachment_name = None
        if "attachment" in request.files:
            file = request.files["attachment"]
            if file and file.filename:
                try:
                    attachment_name = save_quarantined_upload(file)
                except ValueError as ve:
                    flash(str(ve), "danger")
                    return render_template("citizen/submit.html", categories=categories)

        # Category mapping
        cat = db.session.get(Category, category_id) if category_id else None
        if not cat:
            # AI suggestion fallback
            pred = classifier_service.predict(f"{title} {description}")
            cat = Category.query.filter_by(name=pred["predicted_category"]).first() or Category.query.first()

        dept = cat.department if cat else Department.query.first()
        sla_hours = cat.default_sla if cat else 48
        now_utc = datetime.now(timezone.utc)
        deadline = now_utc + timedelta(hours=sla_hours)

        reference = generate_reference_no()
        complaint = Complaint(
            reference_no=reference,
            citizen_id=user_id,
            title=title,
            description=description,
            category_id=cat.id,
            dept_id=dept.id,
            locality=locality,
            latitude=latitude,
            longitude=longitude,
            attachment_path=attachment_name,
            status="SUBMITTED",
            submitted_at=now_utc,
            deadline_at=deadline,
        )
        db.session.add(complaint)
        db.session.flush()

        # Add initial Status History record
        history = ComplaintStatusHistory(
            complaint_id=complaint.id,
            old_status=None,
            new_status="SUBMITTED",
            changed_by_id=user_id,
            remarks="Complaint registered by citizen through web portal.",
        )
        db.session.add(history)
        db.session.commit()

        # Compute transparent priority and scan for duplicates
        update_complaint_priority(complaint)
        record_duplicate_suggestions(complaint)

        log_audit_event("COMPLAINT_SUBMITTED", "complaint", complaint.reference_no, {"locality": locality})
        flash(f"Complaint registered successfully! Reference ID: {reference}", "success")
        return redirect(url_for("citizen.complaint_detail", reference_no=reference))

    return render_template("citizen/submit.html", categories=categories)


@citizen_bp.route("/my-complaints")
@login_required
def my_complaints():
    user_id = session.get("user_id")
    status_filter = request.args.get("status")
    search_query = request.args.get("q", "").strip()

    query = Complaint.query.filter_by(citizen_id=user_id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if search_query:
        query = query.filter(
            (Complaint.title.ilike(f"%{search_query}%"))
            | (Complaint.reference_no.ilike(f"%{search_query}%"))
            | (Complaint.locality.ilike(f"%{search_query}%"))
        )

    complaints = query.order_by(Complaint.submitted_at.desc()).all()
    return render_template("citizen/my_complaints.html", complaints=complaints, selected_status=status_filter, q=search_query)


@citizen_bp.route("/complaint/<reference_no>")
@login_required
@citizen_owns_complaint
def complaint_detail(reference_no):
    complaint = Complaint.query.filter_by(reference_no=reference_no).first_or_404()
    # Filter comments: citizens cannot see internal officer notes
    visible_comments = [c for c in complaint.comments if not c.is_internal]

    return render_template(
        "citizen/detail.html",
        complaint=complaint,
        comments=visible_comments,
    )


@citizen_bp.route("/complaint/<reference_no>/comment", methods=["POST"])
@login_required
@citizen_owns_complaint
def add_comment(reference_no):
    complaint = Complaint.query.filter_by(reference_no=reference_no).first_or_404()
    comment_text = request.form.get("comment", "").strip()
    user_id = session.get("user_id")

    if comment_text:
        comment = ComplaintComment(
            complaint_id=complaint.id,
            author_id=user_id,
            comment=comment_text,
            is_internal=False,
        )
        db.session.add(comment)
        db.session.commit()
        log_audit_event("CITIZEN_COMMENT_ADDED", "complaint", reference_no)
        flash("Follow-up remark posted.", "success")
    else:
        flash("Comment cannot be empty.", "warning")

    return redirect(url_for("citizen.complaint_detail", reference_no=reference_no))


@citizen_bp.route("/complaint/<reference_no>/reopen", methods=["POST"])
@login_required
@citizen_owns_complaint
def reopen_complaint(reference_no):
    complaint = Complaint.query.filter_by(reference_no=reference_no).first_or_404()
    reopen_reason = request.form.get("reason", "").strip()
    user_id = session.get("user_id")

    if complaint.status not in ("RESOLVED", "CLOSED"):
        flash("Only resolved or closed complaints can be reopened.", "warning")
        return redirect(url_for("citizen.complaint_detail", reference_no=reference_no))

    if not reopen_reason:
        flash("A reason is required to dispute resolution and reopen.", "warning")
        return redirect(url_for("citizen.complaint_detail", reference_no=reference_no))

    old_status = complaint.status
    complaint.status = "REOPENED"
    complaint.resolved_at = None

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=old_status,
        new_status="REOPENED",
        changed_by_id=user_id,
        remarks=f"Citizen disputed resolution: {reopen_reason}",
    )
    db.session.add(history)
    db.session.commit()

    update_complaint_priority(complaint)
    log_audit_event("COMPLAINT_REOPENED", "complaint", reference_no, {"reason": reopen_reason})
    flash("Complaint reopened for municipal re-evaluation.", "info")
    return redirect(url_for("citizen.complaint_detail", reference_no=reference_no))
