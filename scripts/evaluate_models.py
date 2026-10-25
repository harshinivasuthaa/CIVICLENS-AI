import sys
import os
from pathlib import Path
import joblib
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.services.ai.classifier import CLASSIFIER_PATH
from app.services.ai.delay_model import DELAY_MODEL_PATH

app = create_app(os.getenv("FLASK_ENV", "development"))


def evaluate_all():
    print("=" * 65)
    print("       CIVICLENS AI — SYSTEM MODEL EVALUATION SUMMARY")
    print("=" * 65)

    # 1. NLP Text Classifier
    print("\n[1] NLP COMPLAINT CLASSIFIER")
    if CLASSIFIER_PATH.exists():
        try:
            bundle = joblib.load(CLASSIFIER_PATH)
            acc = bundle.get("accuracy", "N/A")
            cats = bundle.get("categories", [])
            print(f"  Status:         Model artifact loaded ({CLASSIFIER_PATH.name})")
            print(f"  Test Accuracy:  {acc * 100:.2f}%" if isinstance(acc, float) else f"  Accuracy: {acc}")
            print(f"  Categories ({len(cats)}):")
            for c in cats:
                print(f"    - {c}")
        except Exception as e:
            print(f"  Error loading classifier artifact: {e}")
    else:
        print("  Status: Model not trained yet. Run `python scripts/train_classifier.py`.")

    # 2. Service Delay Risk Model
    print("\n[2] SERVICE DELAY RISK ESTIMATOR")
    if DELAY_MODEL_PATH.exists():
        try:
            bundle = joblib.load(DELAY_MODEL_PATH)
            metrics = bundle.get("metrics", {})
            features = bundle.get("feature_names", [])
            print(f"  Status:         Supervised Random Forest loaded ({DELAY_MODEL_PATH.name})")
            print(f"  Test Accuracy:  {metrics.get('accuracy', 0)*100:.2f}%")
            print(f"  Precision:      {metrics.get('precision', 0)*100:.2f}%")
            print(f"  Recall:         {metrics.get('recall', 0)*100:.2f}%")
            print(f"  F1-Score:       {metrics.get('f1', 0)*100:.2f}%")
            print(f"  ROC-AUC:        {metrics.get('auc', 0):.3f}")
            print(f"  Features ({len(features)}): {', '.join(features)}")
        except Exception as e:
            print(f"  Error loading delay model artifact: {e}")
    else:
        print("  Status: Statistical delay model not trained yet. Baseline heuristic active.")

    print("\n" + "=" * 65)


if __name__ == "__main__":
    evaluate_all()
