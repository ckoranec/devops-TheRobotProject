from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from backend.app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def set_password(self, password):
        if not isinstance(password, str) or len(password) < 12:
            raise ValueError("Password must contain at least 12 characters.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not isinstance(password, str) or not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def is_staff(self):
        return self.role == "staff"
