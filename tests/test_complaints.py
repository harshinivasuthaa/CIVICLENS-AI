from tests.conftest import login_client
from app.models import Complaint, Category, Department, db


def test_complaint_submission(client, app_instance):
    """Verifies that a citizen can register a complaint and receive a unique reference code."""
    login_client(client, "citizen_one", "Citizen@123")

    with app_instance.app_context():
        cat = Category.query.first()
        cat_id = cat.id

    resp = client.post("/citizen/submit", data={
        "title": "Severe road pothole on 4th cross",
        "description": "Pothole filled with rainwater causing skidding.",
        "locality": "Indiranagar",
        "category_id": cat_id,
        "latitude": "12.9716",
        "longitude": "77.5946",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Complaint registered successfully" in resp.data

    with app_instance.app_context():
        c = Complaint.query.filter_by(locality="Indiranagar").first()
        assert c is not None
        assert c.status == "SUBMITTED"
        assert c.reference_no.startswith("CIV-")


def test_complaint_missing_required_fields(client):
    """Verifies validation error when required fields are missing."""
    login_client(client, "citizen_one", "Citizen@123")
    resp = client.post("/citizen/submit", data={
        "title": "",
        "description": "",
        "locality": "",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Title, description, and locality are required" in resp.data


def test_officer_status_update_requires_resolution_notes(client, app_instance):
    """Verifies that an officer cannot mark a complaint RESOLVED without mandatory notes."""
    with app_instance.app_context():
        cat = Category.query.first()
        c = Complaint(
            reference_no="CIV-TEST-RES-001",
            title="Leaking pipe",
            description="Pipe leak test.",
            category_id=cat.id,
            dept_id=cat.dept_id,
            locality="Test Locality",
            status="IN_PROGRESS",
        )
        db.session.add(c)
        db.session.commit()

    login_client(client, "test_officer", "Officer@123")

    # Attempt to mark RESOLVED with empty resolution_notes
    resp = client.post("/officer/complaint/CIV-TEST-RES-001/status", data={
        "status": "RESOLVED",
        "resolution_notes": "",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Resolution notes are strictly required" in resp.data

    # Now mark RESOLVED with valid notes
    resp2 = client.post("/officer/complaint/CIV-TEST-RES-001/status", data={
        "status": "RESOLVED",
        "resolution_notes": "Main valve tightened and pressure tested.",
    }, follow_redirects=True)

    assert resp2.status_code == 200
    assert b"Complaint updated to RESOLVED" in resp2.data

    with app_instance.app_context():
        updated = Complaint.query.filter_by(reference_no="CIV-TEST-RES-001").first()
        assert updated.status == "RESOLVED"
        assert updated.resolved_at is not None
