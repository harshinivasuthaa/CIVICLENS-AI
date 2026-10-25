from datetime import datetime, timezone, timedelta
from .user import db


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    reference_no = db.Column(db.String(64), unique=True, nullable=False, index=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    dept_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True)
    locality = db.Column(db.String(128), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    attachment_path = db.Column(db.String(255), nullable=True)

    # 8-state machine: SUBMITTED, UNDER_REVIEW, ASSIGNED, IN_PROGRESS, RESOLVED, CLOSED, REJECTED, REOPENED
    status = db.Column(db.String(32), default="SUBMITTED", nullable=False, index=True)

    # Priority & Explainability
    suggested_priority = db.Column(db.String(32), default="Routine Review", nullable=False)
    final_priority = db.Column(db.String(32), default="Routine Review", nullable=False)
    priority_score = db.Column(db.Float, default=0.0, nullable=False)
    priority_override_reason = db.Column(db.Text, nullable=True)
    priority_breakdown = db.Column(db.Text, nullable=True)  # JSON-encoded factor scores

    # Delay Risk Estimation
    delay_risk_score = db.Column(db.Float, default=0.0, nullable=False)  # 0.0 to 1.0 probability
    delay_risk_level = db.Column(db.String(32), default="Low Risk", nullable=False)  # Low Risk, Moderate Risk, High Delay Risk
    delay_risk_factors = db.Column(db.Text, nullable=True)  # JSON-encoded explanation factors

    # Lifecycle Timestamps (stored in UTC)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    deadline_at = db.Column(db.DateTime, nullable=True, index=True)
    assigned_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    assigned_officer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    is_synthetic = db.Column(db.Boolean, default=False, nullable=False)
    source_batch_id = db.Column(db.Integer, db.ForeignKey("batch_imports.id"), nullable=True)

    # Relationships
    citizen = db.relationship("User", foreign_keys=[citizen_id], backref="submitted_complaints")
    assigned_officer = db.relationship("User", foreign_keys=[assigned_officer_id], backref="assigned_complaints")
    category = db.relationship("Category", backref="complaints")
    department = db.relationship("Department", backref="complaints")
    status_history = db.relationship("ComplaintStatusHistory", backref="complaint", cascade="all, delete-orphan", order_by="ComplaintStatusHistory.changed_at.desc()")
    comments = db.relationship("ComplaintComment", backref="complaint", cascade="all, delete-orphan", order_by="ComplaintComment.created_at.asc()")
    predictions = db.relationship("AIPredictionRecord", backref="complaint", cascade="all, delete-orphan")

    def is_overdue(self) -> bool:
        """Determines if the complaint has breached its operational SLA."""
        if self.status in ("RESOLVED", "CLOSED", "REJECTED"):
            if self.resolved_at and self.deadline_at:
                return self.resolved_at > self.deadline_at
            return False
        if self.deadline_at:
            now_utc = datetime.now(timezone.utc)
            # handle timezone aware vs naive
            dl = self.deadline_at
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            return now_utc > dl
        return False

    def elapsed_hours(self) -> float:
        """Calculates elapsed hours from submission until resolution or now."""
        now_utc = datetime.now(timezone.utc)
        sub = self.submitted_at
        if sub.tzinfo is None:
            sub = sub.replace(tzinfo=timezone.utc)
        if self.resolved_at:
            res = self.resolved_at
            if res.tzinfo is None:
                res = res.replace(tzinfo=timezone.utc)
            return max(0.0, (res - sub).total_seconds() / 3600.0)
        return max(0.0, (now_utc - sub).total_seconds() / 3600.0)

    def __repr__(self):
        return f"<Complaint {self.reference_no} [{self.status}]>"


class ComplaintStatusHistory(db.Model):
    __tablename__ = "status_history"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    old_status = db.Column(db.String(32), nullable=True)
    new_status = db.Column(db.String(32), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    remarks = db.Column(db.Text, nullable=True)

    changed_by = db.relationship("User", foreign_keys=[changed_by_id])

    def __repr__(self):
        return f"<StatusHistory {self.complaint_id}: {self.old_status} -> {self.new_status}>"


class ComplaintComment(db.Model):
    __tablename__ = "complaint_comments"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False, nullable=False)  # True = Officer only, False = Citizen visible
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    author = db.relationship("User", foreign_keys=[author_id])

    def __repr__(self):
        return f"<ComplaintComment {self.complaint_id} by User {self.author_id}>"
