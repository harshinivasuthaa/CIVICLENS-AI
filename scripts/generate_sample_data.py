import sys
import os
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.models import db, Complaint, Category, Department, User, ComplaintStatusHistory
from app.services.data_engineering import generate_reference_no
from app.services.ai import calculate_priority_score, update_complaint_priority

app = create_app(os.getenv("FLASK_ENV", "development"))

LOCALITIES = [
    ("Indiranagar", 12.9784, 77.6408),
    ("Koramangala", 12.9352, 77.6245),
    ("Whitefield", 12.9698, 77.7500),
    ("Jayanagar", 12.9250, 77.5938),
    ("Malleshwaram", 13.0031, 77.5643),
    ("Rajajinagar", 12.9982, 77.5530),
    ("HSR Layout", 12.9121, 77.6446),
    ("Electronic City", 12.8399, 77.6770),
    ("Basavanagudi", 12.9422, 77.5753),
    ("Hebbal", 13.0358, 77.5970),
]

COMPLAINT_TEMPLATES = {
    "Roads and Potholes": [
        ("Dangerous pothole near junction", "Massive deep pothole on main road causing severe traffic congestion and near accidents."),
        ("Asphalt washed away after rain", "Road surface completely eroded leaving loose stones and slippery mud."),
        ("Broken road divider rebar exposed", "Concrete road divider fractured with hazardous iron rods pointing toward traffic."),
        ("Speed bump damaged and unsignaled", "Speed breaker is broken into sharp chunks without warning stripes."),
        ("Road cave-in near storm drain", "Asphalt caved in creating an abrupt 2-foot sinkhole on the inner service lane."),
    ],
    "Waste Management": [
        ("Garbage dump overflowing for days", "Community waste bin has not been cleared for 4 days, waste spilling onto roadway."),
        ("Illegal commercial plastic dumping", "Truck dumped heaps of packaging plastic waste in open residential plot."),
        ("Missed door-to-door garbage truck", "Waste collection vehicle has skipped our street for three consecutive mornings."),
        ("Dead animal carcass in public alley", "Deceased stray dog lying on sidewalk creating unbearable stench and hygiene hazard."),
        ("Rotting organic waste near school", "Uncollected food waste accumulating near elementary school gate."),
    ],
    "Water Supply": [
        ("Main supply pipeline burst", "High-pressure clean water fountain erupting from underground main pipe."),
        ("Contaminated brown water in tap", "Municipal water received today is murky brown with foul sewage odor."),
        ("No water supply for 48 hours", "Entire apartment sector has received zero water supply despite scheduled release."),
        ("Extremely low distribution pressure", "Water trickle is inadequate to fill household ground sumps."),
        ("Leaking municipal sluice valve", "Valve box is continuously overflowing clean treated water onto road."),
    ],
    "Drainage and Sewage": [
        ("Sewage overflowing into houses", "Underground sewer line choked and raw sewage backing up through toilet drains."),
        ("Open manhole on footpath", "Heavy concrete manhole lid missing, severe fall hazard for pedestrians at night."),
        ("Stormwater drain clogged with trash", "Plastic bottles and silt clogging storm canal leading to stagnant flood water."),
        ("Stagnant black water breeding mosquitoes", "Stagnant drainage ditch uncleaned for months emitting foul swamp gas."),
        ("Culvert concrete slab fractured", "Bridge slab over neighborhood stormwater drain cracked and sagging dangerously."),
    ],
    "Streetlights and Electricity-Related Public Infrastructure": [
        ("Dark road with broken streetlights", "Six consecutive streetlight poles out of order creating pitch dark pedestrian road."),
        ("Exposed electric junction box", "Pedestrian pole junction box door ripped off with live 440V copper wiring exposed."),
        ("Streetlight bulb flickering constantly", "Sodium vapor lamp blinks rapidly causing strobe effect on drivers."),
        ("Electric pole tilting towards house", "Utility pole leaning precariously after heavy monsoon thunderstorm."),
        ("Sparks emerging from transformer pole", "Loud buzzing and visible electric sparks seen on municipal pole transformer."),
    ],
    "Public Sanitation": [
        ("Filthy public toilet without water", "Public sanitation complex near transit depot has clogged toilets and no running tap water."),
        ("Urinal overflow onto sidewalk", "Municipal public urinal choked and effluent draining across footpath."),
        ("Need for bleaching powder spray", "Open alley near fish market requires urgent disinfectant spraying against pest breeding."),
        ("Broken toilet doors in public facility", "Community sanitation unit has damaged privacy doors and non-functional flush."),
        ("Open defecation due to locked restrooms", "Municipal toilet complex locked during peak commuting hours."),
    ],
    "Public Infrastructure": [
        ("Bus shelter roof blown away", "Steel bus stop roof sheared off in windstorm, passengers exposed to sun and rain."),
        ("Children park swing chain broken", "Municipal playground swings fractured with sharp rusted metal exposed."),
        ("Pedestrian skywalk railing rusted", "Foot overbridge safety balustrade missing a 10-foot section over expressway."),
        ("Sidewalk paving tiles dislodged", "Pedestrian walkway tiles uneven and broken, causing senior citizen tripping hazards."),
        ("Boundary wall of civic park leaning", "Brick perimeter wall around public garden cracked and leaning outward."),
    ],
    "Other / Unclassified": [
        ("Stray dog menace and aggressive pack", "Pack of 8 stray dogs chasing evening commuters and school children."),
        ("Illegal loudspeaker noise late at night", "Commercial event playing high-decibel music past 11:30 PM in residential zone."),
        ("Unauthorized footpath encroachment", "Food vendor carts completely blocking public walkway forcing pedestrians onto highway."),
        ("Hazardous tree branch touching cables", "Dead tree bough tangled in electric distribution lines."),
        ("Illegal hoarding blocking junction view", "Giant advertising billboard obstructing driver sightlines at blind turn."),
    ],
}


def generate_synthetic_data(count: int = 500):
    with app.app_context():
        print(f"Generating {count} realistic synthetic complaint records...")
        
        categories = Category.query.all()
        if not categories:
            print("Categories not found. Please run initialize_db.py first.")
            return

        cat_lookup = {c.name: c for c in categories}
        citizens = User.query.filter_by(role="citizen").all()
        officers = User.query.filter_by(role="officer").all()

        now_utc = datetime.now(timezone.utc)
        complaints_created = 0

        for i in range(count):
            cat_name = random.choice(list(COMPLAINT_TEMPLATES.keys()))
            cat_obj = cat_lookup.get(cat_name) or categories[0]
            dept_obj = cat_obj.department

            template_pair = random.choice(COMPLAINT_TEMPLATES[cat_name])
            title = template_pair[0]
            description = template_pair[1]

            loc_info = random.choice(LOCALITIES)
            loc_name = loc_info[0]
            # Add small random jitter (+- 0.015 deg) to coordinates
            lat = round(loc_info[1] + random.uniform(-0.015, 0.015), 5)
            lng = round(loc_info[2] + random.uniform(-0.015, 0.015), 5)

            # Random submission within last 30 days
            days_ago = random.uniform(0.1, 30.0)
            sub_at = now_utc - timedelta(days=days_ago)

            sla_hours = cat_obj.default_sla
            deadline_at = sub_at + timedelta(hours=sla_hours)

            # Determine realistic lifecycle status
            # ~50% resolved/closed, ~35% in progress/assigned/review, ~10% submitted, ~5% rejected/reopened
            rand_roll = random.random()
            if rand_roll < 0.45:
                status = "RESOLVED"
                # Some resolved within SLA, some delayed beyond SLA
                is_delay_case = random.random() < 0.35
                res_duration = sla_hours * (random.uniform(1.1, 2.2) if is_delay_case else random.uniform(0.3, 0.9))
                res_at = sub_at + timedelta(hours=res_duration)
                assigned_at = sub_at + timedelta(hours=random.uniform(1.0, 4.0))
                res_notes = f"Rectified on site by {dept_obj.dept_name} repair team. Inspection completed."
                rej_reason = None
            elif rand_roll < 0.55:
                status = "CLOSED"
                res_duration = sla_hours * random.uniform(0.4, 1.2)
                res_at = sub_at + timedelta(hours=res_duration)
                assigned_at = sub_at + timedelta(hours=random.uniform(1.0, 5.0))
                res_notes = "Field maintenance concluded. Verified and closed."
                rej_reason = None
            elif rand_roll < 0.80:
                status = "IN_PROGRESS"
                res_at = None
                assigned_at = sub_at + timedelta(hours=random.uniform(2.0, 8.0))
                res_notes = None
                rej_reason = None
            elif rand_roll < 0.90:
                status = "ASSIGNED"
                res_at = None
                assigned_at = sub_at + timedelta(hours=random.uniform(1.0, 6.0))
                res_notes = None
                rej_reason = None
            elif rand_roll < 0.95:
                status = "UNDER_REVIEW"
                res_at = None
                assigned_at = None
                res_notes = None
                rej_reason = None
            elif rand_roll < 0.98:
                status = "REOPENED"
                res_at = None
                assigned_at = sub_at + timedelta(hours=3.0)
                res_notes = None
                rej_reason = None
            else:
                status = "REJECTED"
                res_at = None
                assigned_at = None
                res_notes = None
                rej_reason = "Out of municipal territorial jurisdiction; referred to state authority."

            citizen = random.choice(citizens) if citizens else None
            officer = random.choice(officers) if (officers and status in ("ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED")) else None

            complaint = Complaint(
                reference_no=generate_reference_no(),
                citizen_id=citizen.id if citizen else None,
                title=title,
                description=description,
                category_id=cat_obj.id,
                dept_id=dept_obj.id,
                locality=loc_name,
                latitude=lat,
                longitude=lng,
                status=status,
                submitted_at=sub_at,
                deadline_at=deadline_at,
                assigned_at=assigned_at,
                resolved_at=res_at,
                assigned_officer_id=officer.id if officer else None,
                resolution_notes=res_notes,
                rejection_reason=rej_reason,
                is_synthetic=True,
            )
            db.session.add(complaint)
            db.session.flush()

            # Add status history
            hist = ComplaintStatusHistory(
                complaint_id=complaint.id,
                old_status=None,
                new_status=status,
                changed_by_id=officer.id if officer else None,
                remarks=f"Initial seeded record (Status: {status})"
            )
            db.session.add(hist)

            # Compute priority score
            update_complaint_priority(complaint)
            complaints_created += 1

            if complaints_created % 100 == 0:
                db.session.commit()
                print(f"  Created {complaints_created}/{count} complaints...")

        db.session.commit()
        print(f"\nSuccessfully generated {complaints_created} synthetic municipal grievances!")


if __name__ == "__main__":
    generate_synthetic_data(500)
