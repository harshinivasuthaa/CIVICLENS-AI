import sys
import os
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.models import Complaint, Category
from app.services.ai.classifier import normalize_text, ARTIFACTS_DIR, CLASSIFIER_PATH
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

app = create_app(os.getenv("FLASK_ENV", "development"))


def train_classifier():
    with app.app_context():
        print("Loading labeled complaints for NLP text classification...")
        complaints = Complaint.query.all()
        
        data = []
        for c in complaints:
            if c.category and c.title and c.description:
                text = normalize_text(f"{c.title} {c.description}")
                data.append((text, c.category.name))

        if len(data) < 30:
            print("Insufficient records in database to train robust model.")
            return

        texts = [d[0] for d in data]
        labels = [d[1] for d in data]

        print(f"Total labeled dataset size: {len(data)} samples across {len(set(labels))} categories.")

        # Stratified 80/20 train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.20, random_state=42, stratify=labels
        )

        print(f"Training split: {len(X_train)} samples | Test split: {len(X_test)} samples.")

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            max_features=5000,
        )
        X_train_vec = vectorizer.fit_transform(X_train)
        X_test_vec = vectorizer.transform(X_test)

        model = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs", random_state=42)
        model.fit(X_train_vec, y_train)

        # Evaluate on held-out test split (genuine evaluation, never training set)
        y_pred = model.predict(X_test_vec)
        acc = accuracy_score(y_test, y_pred)

        print("\n" + "=" * 60)
        print("  NLP CLASSIFIER EVALUATION REPORT (HELD-OUT TEST SET)")
        print("=" * 60)
        print(f"Overall Accuracy: {acc * 100:.2f}%\n")
        print(classification_report(y_test, y_pred, zero_division=0))

        # Save artifact
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        bundle = {
            "vectorizer": vectorizer,
            "model": model,
            "categories": list(model.classes_),
            "accuracy": round(acc, 4),
        }
        joblib.dump(bundle, CLASSIFIER_PATH)
        print(f"Model artifact successfully saved to: {CLASSIFIER_PATH}")


if __name__ == "__main__":
    train_classifier()
