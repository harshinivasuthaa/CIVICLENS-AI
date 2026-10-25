from .user import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    dept_name = db.Column(db.String(128), unique=True, nullable=False)
    code = db.Column(db.String(32), unique=True, nullable=False)
    sla_hours = db.Column(db.Integer, default=48, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    categories = db.relationship("Category", backref="department", lazy="dynamic")

    def __repr__(self):
        return f"<Department {self.code}: {self.dept_name}>"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    dept_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    default_sla = db.Column(db.Integer, default=48, nullable=False)
    base_severity = db.Column(db.Float, default=0.5, nullable=False)  # Scale: 0.0 (low hazard) to 1.0 (critical hazard)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Category {self.name} (Dept: {self.dept_id})>"
