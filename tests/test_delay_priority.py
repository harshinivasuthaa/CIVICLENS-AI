from app.models import Complaint, Category, Department, db
from app.services.ai.delay_model import delay_service
from app.services.ai.priority import calculate_priority_score, update_complaint_priority
from tests.conftest import login_client


def test_priority_score_range_and_breakdown(app_instance):
    """Verifies that the transparent priority score is bounded in [0, 1] and includes all 5 factors."""
    with app_instance.app_context():
        cat = Category.query.first()
        dept = Department.query.first()
        c = Complaint(
            reference_no="CIV-PRIORITY-001",
            title="Electric wire sparked near kindergarten",
            description="Short circuit sparks falling on sidewalk.",
            category_id=cat.id,
            dept_id=dept.id,
            locality="Indiranagar",
            status="SUBMITTED",
        )
        db.session.add(c)
        db.session.commit()

        res = calculate_priority_score(c)
        assert 0.0 <= res["priority_score"] <= 1.0
        assert res["suggested_priority"] in ("Urgent Review", "Elevated Attention", "Routine Review")
        
        breakdown = res["breakdown"]
        assert "severity" in breakdown
        assert "elapsed_time" in breakdown
        assert "sla_breach" in breakdown
        assert "recurrence" in breakdown
        assert "delay_risk" in breakdown


def test_delay_risk_prediction(app_instance):
    """Verifies delay risk predictor returns probability and operational factors."""
    with app_instance.app_context():
        cat = Category.query.first()
        dept = Department.query.first()
        c = Complaint(
            reference_no="CIV-DELAY-001",
            title="Backlogged drainage issue",
            description="Testing delay risk calculation.",
            category_id=cat.id,
            dept_id=dept.id,
            locality="Koramangala",
            status="SUBMITTED",
        )
        db.session.add(c)
        db.session.commit()

        risk = delay_service.predict_delay_risk(c)
        assert 0.0 <= risk["delay_risk_score"] <= 1.0
        assert risk["delay_risk_level"] in ("Low Risk", "Moderate Risk", "High Delay Risk")
        assert "contributing_factors" in risk


def test_officer_priority_override_justification(client, app_instance):
    """Verifies that an officer priority override is recorded with a mandatory reason."""
    with app_instance.app_context():
        cat = Category.query.first()
        dept = Department.query.first()
        c = Complaint(
            reference_no="CIV-OVERRIDE-001",
            title="Standard grievance",
            description="Regular priority test.",
            category_id=cat.id,
            dept_id=dept.id,
            locality="Jayanagar",
            status="SUBMITTED",
            priority_score=0.25,
            suggested_priority="Routine Review",
            final_priority="Routine Review",
        )
        db.session.add(c)
        db.session.commit()

    login_client(client, "test_officer", "Officer@123")

    # Override without reason should be blocked
    resp_fail = client.post("/officer/complaint/CIV-OVERRIDE-001/override-priority", data={
        "priority": "Urgent Review",
        "reason": "",
    }, follow_redirects=True)
    assert b"A documented reason is mandatory" in resp_fail.data

    # Override with justification should succeed
    resp_pass = client.post("/officer/complaint/CIV-OVERRIDE-001/override-priority", data={
        "priority": "Urgent Review",
        "reason": "VIP delegation route passes through this street tomorrow.",
    }, follow_redirects=True)
    assert b"Priority recommendation updated" in resp_pass.data

    with app_instance.app_context():
        updated = Complaint.query.filter_by(reference_no="CIV-OVERRIDE-001").first()
        assert updated.final_priority == "Urgent Review"
        assert "VIP delegation" in updated.priority_override_reason
