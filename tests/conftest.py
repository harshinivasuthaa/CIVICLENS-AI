import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app import create_app
from app.models import db, User, Department, Category, Complaint, SystemConfig
import json


@pytest.fixture
def app_instance():
    """Create and configure a testing Flask app instance with an isolated in-memory database."""
    app = create_app("testing")

    with app.app_context():
        db.create_all()

        # Seed test departments
        dept_road = Department(dept_name="Roads & Highways", code="ROADS", sla_hours=48, is_active=True)
        dept_waste = Department(dept_name="Solid Waste Management", code="WASTE", sla_hours=24, is_active=True)
        db.session.add_all([dept_road, dept_waste])
        db.session.flush()

        # Seed test categories
        cat_road = Category(name="Roads and Potholes", dept_id=dept_road.id, default_sla=48, base_severity=0.6)
        cat_waste = Category(name="Waste Management", dept_id=dept_waste.id, default_sla=24, base_severity=0.4)
        db.session.add_all([cat_road, cat_waste])
        db.session.flush()

        # Seed priority weights
        weights = {"severity": 0.30, "elapsed_time": 0.25, "sla_breach": 0.20, "recurrence": 0.15, "delay_risk": 0.10}
        cfg = SystemConfig(key="priority_weights", value=json.dumps(weights))
        db.session.add(cfg)

        # Seed test users
        admin = User(username="test_admin", email="admin@test.com", role="admin", is_active=True)
        admin.set_password("Admin@123")

        officer = User(username="test_officer", email="officer@test.com", role="officer", department_id=dept_road.id, is_active=True)
        officer.set_password("Officer@123")

        citizen1 = User(username="citizen_one", email="c1@test.com", role="citizen", is_active=True)
        citizen1.set_password("Citizen@123")

        citizen2 = User(username="citizen_two", email="c2@test.com", role="citizen", is_active=True)
        citizen2.set_password("Citizen@123")

        db.session.add_all([admin, officer, citizen1, citizen2])
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_instance):
    """Test HTTP client."""
    return app_instance.test_client()


def login_client(client, username, password):
    """Helper to authenticate a test client."""
    return client.post("/auth/login", data={"username": username, "password": password}, follow_redirects=True)
