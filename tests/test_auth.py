from tests.conftest import login_client


def test_login_successful(client):
    """Verifies that an authorized user can log in with valid credentials."""
    resp = login_client(client, "test_admin", "Admin@123")
    assert resp.status_code == 200
    assert b"Welcome back, test_admin" in resp.data


def test_login_invalid_password(client):
    """Verifies that incorrect credentials reject authentication."""
    resp = login_client(client, "test_admin", "WrongPassword")
    assert resp.status_code == 200
    assert b"Invalid username or password" in resp.data


def test_logout(client):
    """Verifies that logout invalidates the session."""
    login_client(client, "citizen_one", "Citizen@123")
    resp = client.get("/auth/logout", follow_redirects=True)
    assert resp.status_code == 200
    assert b"securely logged out" in resp.data


def test_role_based_access_restriction(client):
    """Verifies that a citizen role cannot access admin configuration."""
    login_client(client, "citizen_one", "Citizen@123")
    # Admin route should return 403 Forbidden
    resp = client.get("/admin/users")
    assert resp.status_code == 403


def test_citizen_idor_prevention(client, app_instance):
    """Verifies that Citizen A cannot inspect private complaints filed by Citizen B."""
    from app.models import Complaint, Category, Department, User, db
    with app_instance.app_context():
        c1 = User.query.filter_by(username="citizen_one").first()
        c2 = User.query.filter_by(username="citizen_two").first()
        cat = Category.query.first()
        dept = Department.query.first()

        # Create private complaint for citizen_two
        comp = Complaint(
            reference_no="CIV-TEST-IDOR-001",
            citizen_id=c2.id,
            title="Private Citizen Two Grievance",
            description="Confidential private details.",
            category_id=cat.id,
            dept_id=dept.id,
            locality="Test Ward",
            status="SUBMITTED",
        )
        db.session.add(comp)
        db.session.commit()

    # Log in as citizen_one and attempt to access citizen_two's complaint
    login_client(client, "citizen_one", "Citizen@123")
    resp = client.get("/citizen/complaint/CIV-TEST-IDOR-001")
    # Must be blocked with 403 Forbidden
    assert resp.status_code == 403
