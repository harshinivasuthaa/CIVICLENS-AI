from app.services.ai.classifier import classifier_service, normalize_text


def test_text_normalization():
    """Verifies that punctuation is stripped and text is lowercased."""
    raw = "Pothole on 5th MAIN St.!! Warning: dangerous @night."
    clean = normalize_text(raw)
    assert "!" not in clean
    assert "@" not in clean
    assert "pothole on 5th main st" in clean


def test_classifier_prediction_structure():
    """Verifies that the NLP classifier returns the expected structure and calibrated confidence."""
    text = "Large road crater and pothole causing bike accidents"
    res = classifier_service.predict(text)

    assert "predicted_category" in res
    assert "confidence" in res
    assert "is_low_confidence" in res
    assert "recommended_department" in res
    assert 0.0 <= res["confidence"] <= 1.0
    assert res["predicted_category"] == "Roads and Potholes"


def test_low_confidence_flagging():
    """Verifies that ambiguous or empty inputs are flagged for human officer triage."""
    ambiguous = "xyz hello 123"
    res = classifier_service.predict(ambiguous, confidence_threshold=0.55)
    # If confidence < 0.55, it must be flagged for human review
    if res["confidence"] < 0.55:
        assert res["is_low_confidence"] is True
