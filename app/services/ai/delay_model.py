import os
from pathlib import Path
from datetime import datetime, timezone
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from app.models import Complaint, Department, Category, db

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
DELAY_MODEL_PATH = ARTIFACTS_DIR / "delay_model.joblib"


class ServiceDelayPredictor:
    """Predicts service-deadline breach risk using historical operational features or baseline heuristic."""

    def __init__(self):
        self.model = None
        self.feature_names = [
            "category_id",
            "dept_id",
            "day_of_week",
            "hour_of_day",
            "sla_hours",
            "dept_backlog",
            "elapsed_ratio",
        ]
        self.is_loaded = False
        self._load_model()

    def _load_model(self):
        """Attempts to load a pre-trained delay model from disk."""
        if DELAY_MODEL_PATH.exists():
            try:
                bundle = joblib.load(DELAY_MODEL_PATH)
                self.model = bundle["model"]
                self.feature_names = bundle.get("feature_names", self.feature_names)
                self.is_loaded = True
            except Exception:
                self.is_loaded = False

    def train_model(self, min_samples: int = 20):
        """
        Trains a Random Forest delay predictor on historical resolved records.
        Target: is_delayed (1 if resolved_at > deadline_at, else 0).
        """
        resolved_complaints = Complaint.query.filter(
            Complaint.status.in_(["RESOLVED", "CLOSED"]),
            Complaint.resolved_at.isnot(None),
            Complaint.deadline_at.isnot(None),
        ).all()

        if len(resolved_complaints) < min_samples:
            return {
                "success": False,
                "message": f"Insufficient historical records ({len(resolved_complaints)}/{min_samples}) for reliable ML training.",
                "sample_count": len(resolved_complaints),
            }

        X, y = [], []
        for c in resolved_complaints:
            sub = c.submitted_at.replace(tzinfo=timezone.utc) if c.submitted_at.tzinfo is None else c.submitted_at
            res = c.resolved_at.replace(tzinfo=timezone.utc) if c.resolved_at.tzinfo is None else c.resolved_at
            dl = c.deadline_at.replace(tzinfo=timezone.utc) if c.deadline_at.tzinfo is None else c.deadline_at

            sla_hours = (dl - sub).total_seconds() / 3600.0
            elapsed_hours = (res - sub).total_seconds() / 3600.0
            elapsed_ratio = min(2.0, elapsed_hours / max(1.0, sla_hours))

            # Department backlog at submission approximation
            backlog = Complaint.query.filter(
                Complaint.dept_id == c.dept_id,
                Complaint.submitted_at < c.submitted_at,
                Complaint.status.notin_(["RESOLVED", "CLOSED", "REJECTED"]),
            ).count()

            feat = [
                c.category_id,
                c.dept_id,
                sub.weekday(),
                sub.hour,
                sla_hours,
                backlog,
                elapsed_ratio,
            ]
            is_delayed = 1 if res > dl else 0
            X.append(feat)
            y.append(is_delayed)

        X = np.array(X)
        y = np.array(y)

        # Check class balance
        if len(np.unique(y)) < 2:
            return {
                "success": False,
                "message": "All historical records have identical outcomes; cannot train supervised classifier without negative and positive cases.",
                "sample_count": len(y),
            }

        rf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
        rf.fit(X, y)

        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": rf, "feature_names": self.feature_names}, DELAY_MODEL_PATH)
        self.model = rf
        self.is_loaded = True

        return {
            "success": True,
            "message": "Delay prediction model successfully trained.",
            "sample_count": len(y),
            "delay_rate": round(float(np.mean(y)), 3),
        }

    def predict_delay_risk(self, complaint: Complaint) -> dict:
        """
        Estimates the probability that a complaint will breach its configured service deadline.
        Uses Supervised Random Forest if trained, otherwise falls back to deterministic heuristic.
        """
        now_utc = datetime.now(timezone.utc)
        sub = complaint.submitted_at.replace(tzinfo=timezone.utc) if complaint.submitted_at.tzinfo is None else complaint.submitted_at
        
        sla_hours = 48.0
        if complaint.category and complaint.category.default_sla:
            sla_hours = float(complaint.category.default_sla)
        elif complaint.department and complaint.department.sla_hours:
            sla_hours = float(complaint.department.sla_hours)

        elapsed_hours = max(0.0, (now_utc - sub).total_seconds() / 3600.0)
        elapsed_ratio = elapsed_hours / max(1.0, sla_hours)

        # Department backlog count
        dept_backlog = Complaint.query.filter(
            Complaint.dept_id == complaint.dept_id,
            Complaint.status.in_(["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"]),
        ).count()

        contributing_factors = {
            "elapsed_hours": round(elapsed_hours, 1),
            "sla_hours": round(sla_hours, 1),
            "elapsed_ratio": round(elapsed_ratio, 2),
            "department_backlog": dept_backlog,
            "day_of_week": sub.strftime("%A"),
            "submission_hour": sub.hour,
        }

        # Track A: Supervised ML Model
        if self.is_loaded and self.model is not None:
            feat_vector = np.array([[
                complaint.category_id,
                complaint.dept_id,
                sub.weekday(),
                sub.hour,
                sla_hours,
                dept_backlog,
                min(2.0, elapsed_ratio),
            ]])
            try:
                prob = float(self.model.predict_proba(feat_vector)[0][1])
                model_type = "Supervised Random Forest (Trained on Historical Outliers)"
            except Exception:
                prob = self._heuristic_delay_prob(elapsed_ratio, dept_backlog)
                model_type = "Deterministic Operational Baseline"
        else:
            # Track B: Heuristic Baseline
            prob = self._heuristic_delay_prob(elapsed_ratio, dept_backlog)
            model_type = "Deterministic Operational Baseline"

        prob = min(1.0, max(0.0, round(prob, 3)))

        if prob >= 0.70:
            level = "High Delay Risk"
        elif prob >= 0.40:
            level = "Moderate Risk"
        else:
            level = "Low Risk"

        return {
            "delay_risk_score": prob,
            "delay_risk_level": level,
            "model_type": model_type,
            "contributing_factors": contributing_factors,
            "predicted_at": now_utc.isoformat(),
        }

    def _heuristic_delay_prob(self, elapsed_ratio: float, backlog: int) -> float:
        """
        Transparent baseline formula:
        Combines elapsed time proportion (0.60 weight) with departmental backlog pressure (0.40 weight).
        """
        # Baseline probability begins escalating as elapsed time reaches 50% of SLA
        time_component = min(1.0, elapsed_ratio)
        # Backlog component: scales 0 to 1 as active complaints grow from 0 to 20
        backlog_component = min(1.0, backlog / 20.0)
        score = (0.60 * time_component) + (0.40 * backlog_component)
        return score


# Global singleton instance
delay_service = ServiceDelayPredictor()
