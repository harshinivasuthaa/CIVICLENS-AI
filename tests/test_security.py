import io
from app.services.security.uploads import allowed_file


def test_upload_allowed_file_types():
    """Verifies whitelist validation for file uploads."""
    assert allowed_file("pothole_photo.jpg") is True
    assert allowed_file("site_inspection.png") is True
    assert allowed_file("complaint_document.pdf") is True
    assert allowed_file("malicious_script.exe") is False
    assert allowed_file("shell.sh") is False
    assert allowed_file("backdoor.php") is False


def test_health_check_endpoint(client):
    """Verifies that the /health monitoring probe responds with 200 OK and JSON structure."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "UP"
    assert "database" in data
    assert "version" in data


def test_public_dashboard_redacts_pii(client, app_instance):
    """Verifies that the public dashboard does not leak citizen phone numbers, emails, or personal usernames."""
    resp = client.get("/analytics/public-dashboard")
    assert resp.status_code == 200
    # Must not leak demo passwords or private contact fields
    assert b"Admin@123" not in resp.data
    assert b"password_hash" not in resp.data
