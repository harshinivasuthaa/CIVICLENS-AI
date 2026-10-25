from datetime import datetime, timezone
from .user import db


class AIPredictionRecord(db.Model):
    __tablename__ = "ai_predictions"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    prediction_type = db.Column(db.String(64), nullable=False)  # 'category_classification', 'delay_risk'
    prediction_value = db.Column(db.String(128), nullable=False)
    confidence = db.Column(db.Float, nullable=False)  # Calibrated probability or confidence score
    model_version = db.Column(db.String(64), nullable=False)
    explanation_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<AIPrediction {self.prediction_type}: {self.prediction_value} ({self.confidence:.2f})>"


class DuplicateSuggestion(db.Model):
    __tablename__ = "duplicate_suggestions"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    similar_complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    similarity_score = db.Column(db.Float, nullable=False)  # e.g., 0.88
    detection_method = db.Column(db.String(64), default="TFIDF_COSINE_LOCALITY", nullable=False)
    review_status = db.Column(db.String(32), default="PENDING", nullable=False)  # PENDING, CONFIRMED_DUPLICATE, DISMISSED
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    target_complaint = db.relationship("Complaint", foreign_keys=[complaint_id], backref="duplicate_matches")
    similar_complaint = db.relationship("Complaint", foreign_keys=[similar_complaint_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])

    def __repr__(self):
        return f"<DuplicateSuggestion {self.complaint_id} <-> {self.similar_complaint_id} ({self.similarity_score:.2f})>"
