import csv
import io
import json
import hashlib
from datetime import datetime, timezone, timedelta
from app.models import Complaint, Department, Category, BatchImport, User, db
from app.services.ai.classifier import classifier_service, CATEGORY_DEPARTMENT_MAP
from app.services.ai.priority import update_complaint_priority
from app.services.ai.duplicate import record_duplicate_suggestions

DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y %I:%M:%S %p",
]


def parse_timestamp(value: str) -> datetime:
    """Attempts to parse a timestamp string against standard date formats."""
    if not value or not str(value).strip():
        return None
    val = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(val, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: '{val}'")


def generate_reference_no() -> str:
    """Generates unique civic complaint reference code."""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    import random
    suffix = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=6))
    return f"CIV-{now_str}-{suffix}"


def import_complaint_csv(file_stream, filename: str = "upload.csv", source: str = "CSV_IMPORT", is_synthetic: bool = False) -> dict:
    """
    Ingests and validates complaint records from a CSV file.
    Non-destructive quarantine: invalid rows are logged with row numbers and exact reasons.
    """
    try:
        content = file_stream.read()
        if isinstance(content, bytes):
            text = content.decode("utf-8", errors="replace")
        else:
            text = content
        reader = csv.DictReader(io.StringIO(text))
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse CSV stream: {str(e)}",
            "batch_id": None,
        }

    # Normalize field headers (lower, strip)
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    
    # Required columns check
    # We accept: (complaint_text OR description) and (locality)
    has_text = any(h in headers for h in ["complaint_text", "description", "title"])
    has_locality = any(h in headers for h in ["locality", "incident_address", "ward", "location"])

    if not has_text or not has_locality:
        return {
            "success": False,
            "error": "CSV must contain at least a text/description column and a locality/address column.",
            "batch_id": None,
        }

    # Create BatchImport tracking record
    batch = BatchImport(
        filename=filename,
        source=source,
        total_rows=0,
        accepted_rows=0,
        rejected_rows=0,
        status="PROCESSING",
    )
    db.session.add(batch)
    db.session.flush()

    total = 0
    accepted = 0
    rejected = 0
    rejections = []

    # Pre-cache departments and categories for fast mapping
    all_depts = {d.dept_name.lower(): d for d in Department.query.all()}
    all_cats = {c.name.lower(): c for c in Category.query.all()}
    default_dept = Department.query.first()
    default_cat = Category.query.first()

    row_hashes_seen = set()

    for row_idx, raw_row in enumerate(reader, start=2):  # line 1 is header
        total += 1
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw_row.items() if k}

        # Extract text
        title = row.get("title") or row.get("complaint_title") or ""
        desc = row.get("complaint_text") or row.get("description") or row.get("details") or ""
        if not title and desc:
            title = desc[:60] + "..." if len(desc) > 60 else desc
        elif not desc and title:
            desc = title

        locality = row.get("locality") or row.get("incident_address") or row.get("ward") or row.get("location") or ""
        cat_name = row.get("category") or row.get("complaint_type") or ""

        # Validation 1: Required text and locality
        if not title or not desc:
            rejected += 1
            rejections.append({"row": row_idx, "reason": "Missing required complaint title/description."})
            continue

        if not locality:
            rejected += 1
            rejections.append({"row": row_idx, "reason": "Missing required locality or address."})
            continue

        # Validation 2: Deduplication hash check within this batch
        content_hash = hashlib.md5(f"{title}_{locality}".encode("utf-8")).hexdigest()
        if content_hash in row_hashes_seen:
            rejected += 1
            rejections.append({"row": row_idx, "reason": "Duplicate row detected in same upload batch."})
            continue
        row_hashes_seen.add(content_hash)

        # Validation 3: Coordinates if provided
        lat_val = None
        lon_val = None
        raw_lat = row.get("latitude")
        raw_lon = row.get("longitude")
        if raw_lat:
            try:
                lat_float = float(raw_lat)
                if -90.0 <= lat_float <= 90.0:
                    lat_val = lat_float
                else:
                    rejected += 1
                    rejections.append({"row": row_idx, "reason": f"Latitude {lat_float} out of range [-90, 90]."})
                    continue
            except ValueError:
                rejected += 1
                rejections.append({"row": row_idx, "reason": f"Invalid latitude format: '{raw_lat}'."})
                continue

        if raw_lon:
            try:
                lon_float = float(raw_lon)
                if -180.0 <= lon_float <= 180.0:
                    lon_val = lon_float
                else:
                    rejected += 1
                    rejections.append({"row": row_idx, "reason": f"Longitude {lon_float} out of range [-180, 180]."})
                    continue
            except ValueError:
                rejected += 1
                rejections.append({"row": row_idx, "reason": f"Invalid longitude format: '{raw_lon}'."})
                continue

        # Validation 4: Timestamps
        try:
            sub_at = parse_timestamp(row.get("submitted_at") or row.get("created_date")) or datetime.now(timezone.utc)
            res_at = parse_timestamp(row.get("resolved_at") or row.get("closed_date"))
            assigned_at = parse_timestamp(row.get("assigned_at"))

            # Consistency rule: resolved cannot be prior to submitted
            if res_at and res_at < sub_at:
                rejected += 1
                rejections.append({"row": row_idx, "reason": "Inconsistent timestamps: resolved_at is earlier than submitted_at."})
                continue
        except ValueError as ve:
            rejected += 1
            rejections.append({"row": row_idx, "reason": str(ve)})
            continue

        # Match Category & Department
        matched_cat = None
        if cat_name:
            matched_cat = all_cats.get(cat_name.lower())
            if not matched_cat:
                for k, c in all_cats.items():
                    if k in cat_name.lower() or cat_name.lower() in k:
                        matched_cat = c
                        break

        # If not matched or missing, invoke AI classifier
        if not matched_cat:
            pred = classifier_service.predict(f"{title} {desc}")
            matched_cat = all_cats.get(pred["predicted_category"].lower(), default_cat)

        matched_dept = matched_cat.department if (matched_cat and matched_cat.department) else default_dept

        # Status normalization
        raw_status = (row.get("status") or "SUBMITTED").upper()
        valid_statuses = {"SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED", "REJECTED", "REOPENED"}
        status = raw_status if raw_status in valid_statuses else ("RESOLVED" if res_at else "SUBMITTED")

        # Deadline computation
        sla_hours = matched_cat.default_sla if matched_cat else 48
        deadline_at = sub_at + timedelta(hours=sla_hours)

        complaint = Complaint(
            reference_no=row.get("complaint_id") or row.get("reference_no") or generate_reference_no(),
            citizen_id=None,
            title=title[:250],
            description=desc,
            category_id=matched_cat.id if matched_cat else default_cat.id,
            dept_id=matched_dept.id if matched_dept else default_dept.id,
            locality=locality[:120],
            latitude=lat_val,
            longitude=lon_val,
            status=status,
            submitted_at=sub_at,
            deadline_at=deadline_at,
            assigned_at=assigned_at,
            resolved_at=res_at,
            resolution_notes=row.get("resolution_notes") or ("Resolved per field team report" if status in ("RESOLVED", "CLOSED") else None),
            is_synthetic=is_synthetic,
            source_batch_id=batch.id,
        )
        db.session.add(complaint)
        accepted += 1

    # Commit accepted records
    batch.total_rows = total
    batch.accepted_rows = accepted
    batch.rejected_rows = rejected
    batch.rejection_summary_json = json.dumps(rejections[:100])  # store top 100 rejections
    batch.status = "COMPLETED"
    db.session.commit()

    return {
        "success": True,
        "batch_id": batch.id,
        "total_rows": total,
        "accepted_rows": accepted,
        "rejected_rows": rejected,
        "rejections": rejections,
    }
