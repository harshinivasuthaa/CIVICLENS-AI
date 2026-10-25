import os
import re
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
CLASSIFIER_PATH = ARTIFACTS_DIR / "classifier.joblib"

# Supported municipal categories (8 categories)
DEFAULT_CATEGORIES = [
    "Roads and Potholes",
    "Waste Management",
    "Water Supply",
    "Drainage and Sewage",
    "Streetlights and Electricity-Related Public Infrastructure",
    "Public Sanitation",
    "Public Infrastructure",
    "Other / Unclassified",
]

# Category to Department mappings
CATEGORY_DEPARTMENT_MAP = {
    "Roads and Potholes": "Roads & Highways",
    "Waste Management": "Solid Waste Management",
    "Water Supply": "Water Supply & Sewerage",
    "Drainage and Sewage": "Stormwater & Drainage",
    "Streetlights and Electricity-Related Public Infrastructure": "Electrical & Lighting",
    "Public Sanitation": "Public Health & Sanitation",
    "Public Infrastructure": "Public Works & Infrastructure",
    "Other / Unclassified": "General Municipal Administration",
}

# Seed corpus for initial training / fallback so the system is immediately functional
INITIAL_CORPUS = [
    # Roads and Potholes
    ("Huge pothole on 5th main road causing bike accidents", "Roads and Potholes"),
    ("Asphalt washed away after rain, deep crater in front of community center", "Roads and Potholes"),
    ("Cracked road surface and dangerous road divider damage", "Roads and Potholes"),
    ("Road cave in near bus stop, hazardous driving conditions", "Roads and Potholes"),
    ("Speed breaker broken with exposed iron rebar", "Roads and Potholes"),
    ("Tar peeled off road surface leaving slippery loose gravel", "Roads and Potholes"),
    # Waste Management
    ("Garbage dump overflowing on street corner for three days", "Waste Management"),
    ("Illegal dumping of commercial plastic waste in open plot", "Waste Management"),
    ("Door to door garbage collection truck has not visited all week", "Waste Management"),
    ("Dead animal carcass lying near market entrance, foul odor", "Waste Management"),
    ("Municipal trash bin overturned and rotting waste scattered", "Waste Management"),
    ("Construction debris dumped on sidewalk blocking pedestrians", "Waste Management"),
    # Water Supply
    ("No municipal water supply in residential block for 48 hours", "Water Supply"),
    ("Drinking water pipeline burst and clean water flooding the street", "Water Supply"),
    ("Contaminated tap water with brown muddy color and foul chemical smell", "Water Supply"),
    ("Extremely low water pressure in colony borewell distribution lines", "Water Supply"),
    ("Water tanker requested for dry sector not arrived", "Water Supply"),
    ("Underground main pipeline valve leaking profusely", "Water Supply"),
    # Drainage and Sewage
    ("Sewage overflowing from manhole and entering ground floor houses", "Drainage and Sewage"),
    ("Stormwater drain clogged with plastic bottles, localized street flooding", "Drainage and Sewage"),
    ("Open manhole cover stolen, severe safety hazard for pedestrians", "Drainage and Sewage"),
    ("Drainage line backflow during monsoon shower", "Drainage and Sewage"),
    ("Stagnant black sewage water breeding mosquitoes in alley", "Drainage and Sewage"),
    ("Broken concrete slab over storm drain collapsed", "Drainage and Sewage"),
    # Streetlights and Electricity
    ("Streetlights not working on entire stretch of MG Road, completely dark", "Streetlights and Electricity-Related Public Infrastructure"),
    ("Flickering halogen streetlight bulb keeps turning off", "Streetlights and Electricity-Related Public Infrastructure"),
    ("Electric junction box hanging open with exposed live wires", "Streetlights and Electricity-Related Public Infrastructure"),
    ("Electric pole tilting dangerously after truck collision", "Streetlights and Electricity-Related Public Infrastructure"),
    ("Park floodlights remain dark every night", "Streetlights and Electricity-Related Public Infrastructure"),
    ("Short circuit sparks seen on municipal transformer pole", "Streetlights and Electricity-Related Public Infrastructure"),
    # Public Sanitation
    ("Public toilet near bus terminus is filthy with no running water", "Public Sanitation"),
    ("Community urinal choked and overflowing onto public footpath", "Public Sanitation"),
    ("Lack of disinfectant bleaching powder near vegetable market", "Public Sanitation"),
    ("Urinal facility door broken and sanitary conditions unhygienic", "Public Sanitation"),
    ("Open defecation along railway boundary due to locked public restrooms", "Public Sanitation"),
    ("Bio-toilet unit filled and non-functional", "Public Sanitation"),
    # Public Infrastructure
    ("Bus stop shelter roof collapsed in heavy wind", "Public Infrastructure"),
    ("Public park perimeter fence and children swing broken", "Public Infrastructure"),
    ("Foot overbridge railing rusted and missing safety barrier", "Public Infrastructure"),
    ("Pedestrian sidewalk tiles broken and uneven causing falls", "Public Infrastructure"),
    ("Municipal community hall boundary wall cracked and crumbling", "Public Infrastructure"),
    ("Subway underpass pedestrian ramp submerged and impassable", "Public Infrastructure"),
    # Other / Unclassified
    ("Stray dog menace and aggressive pack barking at passersby", "Other / Unclassified"),
    ("Loud illegal loudspeakers blasting after midnight in residential zone", "Other / Unclassified"),
    ("Encroachment on public footpath by unauthorized vendor stalls", "Other / Unclassified"),
    ("Request for tree pruning as branches touch overhead cables", "Other / Unclassified"),
    ("Unregistered commercial hoarding blocking traffic visibility", "Other / Unclassified"),
]


def normalize_text(text: str) -> str:
    """Preprocesses raw complaint text: lowercasing, punctuation stripping, whitespace normalization."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class ComplaintClassifier:
    """TF-IDF and Multinomial Logistic Regression complaint categorization model."""

    def __init__(self):
        self.model = None
        self.vectorizer = None
        self.categories = DEFAULT_CATEGORIES
        self.is_loaded = False
        self._load_or_train()

    def _load_or_train(self):
        """Loads serialized model or bootstraps using seed corpus."""
        if CLASSIFIER_PATH.exists():
            try:
                bundle = joblib.load(CLASSIFIER_PATH)
                self.vectorizer = bundle["vectorizer"]
                self.model = bundle["model"]
                self.categories = bundle["categories"]
                self.is_loaded = True
                return
            except Exception:
                pass

        # Train initial bootstrap model
        self.train_and_save(INITIAL_CORPUS)

    def train_and_save(self, corpus):
        """Trains the TF-IDF and Logistic Regression pipeline on labeled complaint pairs."""
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        texts = [normalize_text(item[0]) for item in corpus]
        labels = [item[1] for item in corpus]

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            max_features=5000,
        )
        X = self.vectorizer.fit_transform(texts)

        self.model = LogisticRegression(
            C=1.0,
            max_iter=1000,
            solver="lbfgs",
            random_state=42,
        )
        self.model.fit(X, labels)
        self.categories = list(self.model.classes_)
        self.is_loaded = True

        bundle = {
            "vectorizer": self.vectorizer,
            "model": self.model,
            "categories": self.categories,
        }
        joblib.dump(bundle, CLASSIFIER_PATH)

    def predict(self, text: str, confidence_threshold: float = 0.55):
        """
        Classifies complaint text.
        Returns:
            dict with:
                - predicted_category: str
                - confidence: float (0.0 to 1.0)
                - is_low_confidence: bool
                - recommended_department: str
                - top_alternatives: list of (category, prob)
                - model_version: str
        """
        cleaned = normalize_text(text)
        if not cleaned or not self.is_loaded:
            return {
                "predicted_category": "Other / Unclassified",
                "confidence": 0.0,
                "is_low_confidence": True,
                "recommended_department": "General Municipal Administration",
                "top_alternatives": [],
                "model_version": "TFIDF-LogReg-v1.0 (Fallback)",
            }

        X = self.vectorizer.transform([cleaned])
        probs = self.model.predict_proba(X)[0]
        classes = self.model.classes_

        ranked_indices = probs.argsort()[::-1]
        best_idx = ranked_indices[0]
        best_cat = classes[best_idx]
        best_prob = float(probs[best_idx])

        top_alternatives = [
            {"category": classes[idx], "confidence": round(float(probs[idx]), 3)}
            for idx in ranked_indices[1:4]
        ]

        is_low_conf = best_prob < confidence_threshold
        rec_dept = CATEGORY_DEPARTMENT_MAP.get(best_cat, "General Municipal Administration")

        return {
            "predicted_category": best_cat,
            "confidence": round(best_prob, 3),
            "is_low_confidence": is_low_conf,
            "recommended_department": rec_dept,
            "top_alternatives": top_alternatives,
            "model_version": "TFIDF-LogReg-v1.0",
        }


# Global singleton instance
classifier_service = ComplaintClassifier()
