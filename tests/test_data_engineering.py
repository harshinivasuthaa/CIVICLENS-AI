import io
from app.services.data_engineering.importer import import_complaint_csv
from app.services.data_engineering.quality import generate_data_quality_report
from app.models import Complaint, BatchImport


def test_valid_csv_import(app_instance):
    """Verifies that well-formed CSV complaints are parsed and accepted."""
    csv_data = """title,description,locality,category,latitude,longitude
"Road Pothole","Large pothole on highway","Basavanagudi","Roads and Potholes",12.9422,77.5753
"Overflowing Dustbin","Waste bin spilling onto road","Koramangala","Waste Management",12.9352,77.6245
"""
    stream = io.StringIO(csv_data)
    with app_instance.app_context():
        res = import_complaint_csv(stream, filename="test_valid.csv")
        assert res["success"] is True
        assert res["total_rows"] == 2
        assert res["accepted_rows"] == 2
        assert res["rejected_rows"] == 0


def test_malformed_csv_quarantine(app_instance):
    """Verifies that rows with corrupt coordinates or missing localities are quarantined without crashing."""
    csv_data = """title,description,locality,latitude,longitude
"Valid Issue","Valid complaint text","Whitefield",12.9698,77.7500
"Corrupt Coords","Latitude is out of range","Hebbal",999.0,77.5970
"Missing Locality","Where did this occur?","",12.9716,77.5946
"""
    stream = io.StringIO(csv_data)
    with app_instance.app_context():
        res = import_complaint_csv(stream, filename="test_malformed.csv")
        assert res["success"] is True
        assert res["total_rows"] == 3
        assert res["accepted_rows"] == 1
        assert res["rejected_rows"] == 2
        assert len(res["rejections"]) == 2


def test_data_quality_report(app_instance):
    """Verifies data quality computation completeness score."""
    with app_instance.app_context():
        report = generate_data_quality_report()
        assert "completeness_score" in report
        assert "missing_coords_pct" in report
        assert isinstance(report["completeness_score"], float)
