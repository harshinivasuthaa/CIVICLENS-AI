from datetime import datetime, timezone, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.models import Complaint, DuplicateSuggestion, db
from .classifier import normalize_text


def find_similar_complaints(
    title: str,
    description: str,
    locality: str,
    exclude_id: int = None,
    time_window_days: int = 14,
    limit: int = 5,
):
    """
    Identifies potentially duplicate or related complaints within the spatiotemporal window.
    Evaluates TF-IDF Cosine Similarity between the incoming complaint and candidate pool.
    """
    query_text = normalize_text(f"{title} {description}")
    if not query_text:
        return []

    # Spatiotemporal filter: candidate pool in same locality within window
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=time_window_days)

    query = Complaint.query.filter(
        Complaint.locality.ilike(f"%{locality.strip()}%"),
        Complaint.submitted_at >= cutoff,
    )
    if exclude_id:
        query = query.filter(Complaint.id != exclude_id)

    candidates = query.all()
    if not candidates:
        return []

    candidate_texts = [
        normalize_text(f"{c.title} {c.description}") for c in candidates
    ]

    all_texts = [query_text] + candidate_texts
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    try:
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        # Cosine similarity between query (index 0) and all candidates (index 1..)
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])[0]
    except Exception:
        return []

    results = []
    for candidate, score in zip(candidates, similarities):
        score_val = round(float(score), 3)
        if score_val >= 0.65:
            if score_val >= 0.85:
                match_tier = "High Similarity (Probable Duplicate)"
                reason = f"High textual overlap ({int(score_val*100)}%) in the same locality within {time_window_days} days."
            else:
                match_tier = "Moderate Similarity (Related Chronic Issue)"
                reason = f"Noticeable topical similarity ({int(score_val*100)}%) regarding {candidate.category.name if candidate.category else 'infrastructure'} in {locality}."

            results.append({
                "complaint_id": candidate.id,
                "reference_no": candidate.reference_no,
                "title": candidate.title,
                "locality": candidate.locality,
                "category": candidate.category.name if candidate.category else "Unclassified",
                "status": candidate.status,
                "submitted_at": candidate.submitted_at.isoformat(),
                "similarity_score": score_val,
                "match_tier": match_tier,
                "reason": reason,
            })

    # Sort descending by similarity score
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:limit]


def record_duplicate_suggestions(complaint: Complaint):
    """Detects and saves duplicate suggestions into the database non-destructively."""
    matches = find_similar_complaints(
        title=complaint.title,
        description=complaint.description,
        locality=complaint.locality,
        exclude_id=complaint.id,
    )

    for match in matches:
        existing = DuplicateSuggestion.query.filter_by(
            complaint_id=complaint.id,
            similar_complaint_id=match["complaint_id"],
        ).first()

        if not existing:
            suggestion = DuplicateSuggestion(
                complaint_id=complaint.id,
                similar_complaint_id=match["complaint_id"],
                similarity_score=match["similarity_score"],
                detection_method="TFIDF_COSINE_LOCALITY",
                review_status="PENDING",
            )
            db.session.add(suggestion)

    db.session.commit()
