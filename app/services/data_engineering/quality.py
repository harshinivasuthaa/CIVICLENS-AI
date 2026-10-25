from datetime import datetime, timezone
import numpy as np
from app.models import Complaint, BatchImport, Category, Department, db


def generate_data_quality_report() -> dict:
    """
    Computes data-quality metrics across the complaint database:
    - Completeness percentage
    - Missing coordinate rate
    - Timestamp validity and consistency
    - Category distribution
    - Batch import acceptance rates
    """
    total = Complaint.query.count()
    if total == 0:
        return {
            "total_records": 0,
            "completeness_score": 100.0,
            "missing_coords_count": 0,
            "missing_coords_pct": 0.0,
            "missing_resolution_resolved_count": 0,
            "overdue_active_count": 0,
            "category_distribution": {},
            "batch_summary": [],
        }

    # Missing coordinates
    missing_coords = Complaint.query.filter(
        (Complaint.latitude.is_(None)) | (Complaint.longitude.is_(None))
    ).count()

    # Inconsistent resolved records (status is RESOLVED/CLOSED but resolved_at is null)
    inconsistent_res = Complaint.query.filter(
        Complaint.status.in_(["RESOLVED", "CLOSED"]),
        Complaint.resolved_at.is_(None),
    ).count()

    # Active complaints overdue
    now_utc = datetime.now(timezone.utc)
    all_active = Complaint.query.filter(
        Complaint.status.in_(["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"]),
        Complaint.deadline_at.isnot(None),
    ).all()
    overdue_active = sum(1 for c in all_active if c.is_overdue())

    # Category distribution
    cat_counts = {}
    categories = Category.query.all()
    for cat in categories:
        cnt = Complaint.query.filter_by(category_id=cat.id).count()
        cat_counts[cat.name] = cnt

    # Batch imports
    batches = BatchImport.query.order_by(BatchImport.imported_at.desc()).limit(10).all()
    batch_list = []
    total_batch_rows = 0
    total_batch_accepted = 0
    for b in batches:
        total_batch_rows += b.total_rows
        total_batch_accepted += b.accepted_rows
        rate = round((b.accepted_rows / b.total_rows * 100), 1) if b.total_rows > 0 else 100.0
        batch_list.append({
            "id": b.id,
            "filename": b.filename,
            "source": b.source,
            "total": b.total_rows,
            "accepted": b.accepted_rows,
            "rejected": b.rejected_rows,
            "acceptance_rate": rate,
            "imported_at": b.imported_at.strftime("%Y-%m-%d %H:%M"),
        })

    # Overall completeness index: based on presence of coordinates, valid category, timestamps
    completeness = round(100.0 - (missing_coords / total * 30.0) - (inconsistent_res / total * 50.0), 1)
    completeness = max(0.0, min(100.0, completeness))

    return {
        "total_records": total,
        "completeness_score": completeness,
        "missing_coords_count": missing_coords,
        "missing_coords_pct": round(missing_coords / total * 100, 1),
        "inconsistent_resolved_count": inconsistent_res,
        "overdue_active_count": overdue_active,
        "category_distribution": cat_counts,
        "batch_summary": batch_list,
        "batch_acceptance_rate": round(total_batch_accepted / max(1, total_batch_rows) * 100, 1) if total_batch_rows > 0 else 100.0,
    }
