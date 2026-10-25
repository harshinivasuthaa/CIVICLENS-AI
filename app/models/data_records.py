from datetime import datetime, timezone
from .user import db


class BatchImport(db.Model):
    __tablename__ = "batch_imports"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    source = db.Column(db.String(128), default="MUNICIPAL_CSV", nullable=False)
    total_rows = db.Column(db.Integer, default=0, nullable=False)
    accepted_rows = db.Column(db.Integer, default=0, nullable=False)
    rejected_rows = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(32), default="COMPLETED", nullable=False)  # PROCESSING, COMPLETED, FAILED
    rejection_summary_json = db.Column(db.Text, nullable=True)  # Detailed per-row errors
    imported_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    complaints = db.relationship("Complaint", backref="import_batch", lazy="dynamic")

    def __repr__(self):
        return f"<BatchImport {self.id}: {self.filename} ({self.accepted_rows}/{self.total_rows} accepted)>"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    actor_role = db.Column(db.String(32), nullable=True)
    action = db.Column(db.String(128), nullable=False, index=True)  # e.g. STATUS_UPDATE, PRIORITY_OVERRIDE, CSV_IMPORT
    entity_type = db.Column(db.String(64), nullable=False, index=True)  # complaint, user, batch_import, system_config
    entity_id = db.Column(db.String(64), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    details_json = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    actor = db.relationship("User", foreign_keys=[actor_id])

    def __repr__(self):
        return f"<AuditLog {self.action} on {self.entity_type} {self.entity_id} by User {self.actor_id}>"


class SystemConfig(db.Model):
    __tablename__ = "system_configs"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<SystemConfig {self.key}={self.value}>"
