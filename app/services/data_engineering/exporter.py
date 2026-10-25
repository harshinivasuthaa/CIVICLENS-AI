import csv
import io
from flask import Response
from app.models import Complaint


def export_complaints_csv(query, include_pii: bool = False) -> Response:
    """
    Exports filtered complaint records as a downloadable CSV.
    Omits citizen email/phone and masks internal notes unless include_pii is explicitly authorized.
    """
    complaints = query.all()
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    headers = [
        "reference_no",
        "title",
        "category",
        "department",
        "locality",
        "latitude",
        "longitude",
        "status",
        "priority_score",
        "suggested_priority",
        "final_priority",
        "delay_risk_level",
        "submitted_at",
        "deadline_at",
        "resolved_at",
    ]
    if include_pii:
        headers.extend(["citizen_username", "assigned_officer", "resolution_notes"])

    writer.writerow(headers)

    for c in complaints:
        row = [
            c.reference_no,
            c.title,
            c.category.name if c.category else "",
            c.department.dept_name if c.department else "",
            c.locality,
            c.latitude if c.latitude is not None else "",
            c.longitude if c.longitude is not None else "",
            c.status,
            c.priority_score,
            c.suggested_priority,
            c.final_priority,
            c.delay_risk_level,
            c.submitted_at.isoformat() if c.submitted_at else "",
            c.deadline_at.isoformat() if c.deadline_at else "",
            c.resolved_at.isoformat() if c.resolved_at else "",
        ]
        if include_pii:
            row.extend([
                c.citizen.username if c.citizen else "Anonymous/Batch",
                c.assigned_officer.username if c.assigned_officer else "Unassigned",
                c.resolution_notes or "",
            ])
        writer.writerow(row)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=civiclens_complaints_report.csv"},
    )
