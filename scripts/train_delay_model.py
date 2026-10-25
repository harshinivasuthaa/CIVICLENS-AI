import sys
import os
from pathlib import Path
from datetime import timezone
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.models import Complaint
from app.services.ai.delay_model import ARTIFACTS_DIR, DELAY_MODEL_PATH

app = create_app(os.getenv("FLASK_ENV", "development"))


def train_delay_model():
    with app.app_context():
        print("Extracting historical resolved grievances for delay risk modeling...")
        resolved = Complaint.query.filter(
            Complaint.status.in_(["RESOLVED", "CLOSED"]),
            Complaint.resolved_at.isnot(None),
            Complaint.deadline_at.isnot(None),
        ).all()

        if len(resolved) < 20:
            print(f"Insufficient historical resolved records ({len(resolved)}/20) for statistical modeling.")
            return

        X, y = [], []
        feature_names = [
            "category_id",
            "dept_id",
            "day_of_week",
            "hour_of_day",
            "sla_hours",
            "dept_backlog",
            "elapsed_ratio",
        ]

        for c in resolved:
            sub = c.submitted_at.replace(tzinfo=timezone.utc) if c.submitted_at.tzinfo is None else c.submitted_at
            res = c.resolved_at.replace(tzinfo=timezone.utc) if c.resolved_at.tzinfo is None else c.resolved_at
            dl = c.deadline_at.replace(tzinfo=timezone.utc) if c.deadline_at.tzinfo is None else c.deadline_at

            sla_hours = (dl - sub).total_seconds() / 3600.0
            elapsed_hours = (res - sub).total_seconds() / 3600.0
            elapsed_ratio = min(2.0, elapsed_hours / max(1.0, sla_hours))

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

        print(f"Loaded {len(X)} eligible historical records. Positive delay cases: {np.sum(y)} ({np.mean(y)*100:.1f}%)")

        if len(np.unique(y)) < 2:
            print("Target labels have zero variance (single class). Cannot train binary classifier.")
            return

        # Train / test split (80/20)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42, stratify=y
        )

        model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
        model.fit(X_train, y_train)

        # Held-out evaluation
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        auc = roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else 0.5

        print("\n" + "=" * 60)
        print("  SERVICE DELAY PREDICTION EVALUATION REPORT (TEST SET)")
        print("=" * 60)
        print(f"Accuracy:  {acc * 100:.2f}%")
        print(f"Precision: {prec * 100:.2f}%")
        print(f"Recall:    {rec * 100:.2f}%")
        print(f"F1-Score:  {f1 * 100:.2f}%")
        print(f"ROC-AUC:   {auc:.3f}\n")

        print("Feature Importances:")
        for name, imp in zip(feature_names, model.feature_importances_):
            print(f"  - {name:15s}: {imp:.4f}")

        # Save model
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        bundle = {
            "model": model,
            "feature_names": feature_names,
            "metrics": {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "auc": auc},
        }
        joblib.dump(bundle, DELAY_MODEL_PATH)
        print(f"\nDelay risk model artifact saved to: {DELAY_MODEL_PATH}")


if __name__ == "__main__":
    train_delay_model()
