import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.models import db, User, Department, Category, SystemConfig

app = create_app(os.getenv("FLASK_ENV", "development"))


def init_database():
    with app.app_context():
        print("Initializing database tables...")
        db.create_all()

        # 1. Seed Departments
        dept_data = [
            ("Roads & Highways", "ROADS", 48),
            ("Solid Waste Management", "WASTE", 24),
            ("Water Supply & Sewerage", "WATER", 36),
            ("Stormwater & Drainage", "DRAINAGE", 48),
            ("Electrical & Lighting", "ELECTRICAL", 24),
            ("Public Health & Sanitation", "SANITATION", 24),
            ("Public Works & Infrastructure", "INFRA", 72),
            ("General Municipal Administration", "GENERAL", 96),
        ]

        dept_map = {}
        for name, code, sla in dept_data:
            dept = Department.query.filter_by(code=code).first()
            if not dept:
                dept = Department(dept_name=name, code=code, sla_hours=sla, is_active=True)
                db.session.add(dept)
                db.session.flush()
                print(f"Created Department: {name} ({code})")
            dept_map[name] = dept

        # 2. Seed Categories
        cat_data = [
            ("Roads and Potholes", "Roads & Highways", 48, 0.6, "Potholes, road cave-ins, loose gravel, broken dividers"),
            ("Waste Management", "Solid Waste Management", 24, 0.4, "Overflowing dustbins, missed door-to-door collection, animal carcasses"),
            ("Water Supply", "Water Supply & Sewerage", 36, 0.7, "Pipeline bursts, low pressure, contaminated discolored water"),
            ("Drainage and Sewage", "Stormwater & Drainage", 48, 0.7, "Choked drains, open manholes, sewage backflow into homes"),
            ("Streetlights and Electricity-Related Public Infrastructure", "Electrical & Lighting", 24, 0.5, "Malfunctioning streetlights, exposed live wires, sparkings"),
            ("Public Sanitation", "Public Health & Sanitation", 24, 0.5, "Unclean public restrooms, community urination, disinfection"),
            ("Public Infrastructure", "Public Works & Infrastructure", 72, 0.5, "Damaged bus stops, broken foot overbridges, crumbling sidewalks"),
            ("Other / Unclassified", "General Municipal Administration", 96, 0.3, "Noise pollution, stray animal menace, general grievances"),
        ]

        for name, dept_name, sla, base_sev, desc in cat_data:
            cat = Category.query.filter_by(name=name).first()
            dept = dept_map.get(dept_name)
            if not cat and dept:
                cat = Category(name=name, dept_id=dept.id, default_sla=sla, base_severity=base_sev, description=desc)
                db.session.add(cat)
                print(f"Created Category: {name}")

        # 3. Seed Priority Formula System Config
        cfg = SystemConfig.query.filter_by(key="priority_weights").first()
        if not cfg:
            default_weights = {
                "severity": 0.30,
                "elapsed_time": 0.25,
                "sla_breach": 0.20,
                "recurrence": 0.15,
                "delay_risk": 0.10,
            }
            cfg = SystemConfig(
                key="priority_weights",
                value=json.dumps(default_weights),
                description="Composite prioritization formula weights",
            )
            db.session.add(cfg)
            print("Seeded default priority weights configuration.")

        # 4. Seed Fictional Demonstration Users
        road_dept = Department.query.filter_by(code="ROADS").first()
        waste_dept = Department.query.filter_by(code="WASTE").first()

        users_to_seed = [
            ("admin", "admin@civiclens.local", "Admin@123", "admin", None),
            ("officer_road", "officer.road@civiclens.local", "Officer@123", "officer", road_dept.id if road_dept else None),
            ("officer_waste", "officer.waste@civiclens.local", "Officer@123", "officer", waste_dept.id if waste_dept else None),
            ("citizen_jane", "jane.citizen@example.com", "Citizen@123", "citizen", None),
            ("citizen_john", "john.citizen@example.com", "Citizen@123", "citizen", None),
        ]

        for username, email, pwd, role, dept_id in users_to_seed:
            u = User.query.filter_by(username=username).first()
            if not u:
                u = User(username=username, email=email, role=role, department_id=dept_id, is_active=True)
                u.set_password(pwd)
                db.session.add(u)
                print(f"Created Demo User: {username} ({role})")

        db.session.commit()
        print("\nDatabase initialization complete! Ready for local execution.")


if __name__ == "__main__":
    init_database()
