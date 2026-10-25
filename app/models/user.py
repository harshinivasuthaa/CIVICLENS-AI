from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

# Will be initialized in extensions / app factory
db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="citizen", index=True)  # admin, officer, citizen, public
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    department = db.relationship("Department", backref="officers", foreign_keys=[department_id])

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_officer(self) -> bool:
        return self.role in ("officer", "admin")

    def is_citizen(self) -> bool:
        return self.role == "citizen"

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
