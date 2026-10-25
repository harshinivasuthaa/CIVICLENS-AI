from flask import Blueprint, request, jsonify
from app.services.ai.classifier import classifier_service
from app.services.ai.duplicate import find_similar_complaints

ai_api_bp = Blueprint("ai_api", __name__)


@ai_api_bp.route("/predict-category", methods=["POST"])
def predict_category():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    result = classifier_service.predict(text)
    return jsonify(result), 200


@ai_api_bp.route("/check-duplicates", methods=["POST"])
def check_duplicates():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    locality = data.get("locality", "").strip()

    if not title or not locality:
        return jsonify({"matches": []}), 200

    matches = find_similar_complaints(title=title, description=description, locality=locality)
    return jsonify({"matches": matches}), 200
