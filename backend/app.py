from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import SQLAlchemyError

db = SQLAlchemy()


class ContactSubmission(db.Model):
    __tablename__ = "contact_submissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


def create_app(test_config=None):
    app = Flask(__name__)

    database_path = Path(__file__).resolve().parent.parent / "instance" / "max_byte.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path.as_posix()}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=16384,
        JSON_SORT_KEYS=False,
    )

    if test_config:
        app.config.update(test_config)

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[],
        storage_uri="memory://",
    )

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", service="MAX Byte API")

    @app.post("/api/contact")
    @limiter.limit("5 per minute")
    def submit_contact():
        if not request.is_json:
            return jsonify(error="JSON request required"), 415

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify(error="Invalid JSON object"), 400

        name = data.get("name")
        email = data.get("email")
        message = data.get("message")

        if not all(isinstance(x, str) for x in (name, email, message)):
            return jsonify(error="Name, email and message are required"), 400

        name = name.strip()
        email = email.strip()
        message = message.strip()

        if not (1 <= len(name) <= 120):
            return jsonify(error="Invalid name"), 400

        if (
            not (3 <= len(email) <= 254)
            or email.count("@") != 1
            or "." not in email.rsplit("@", 1)[-1]
            or any(c.isspace() for c in email)
        ):
            return jsonify(error="Invalid email address"), 400

        if not (1 <= len(message) <= 5000):
            return jsonify(error="Message must contain 1 to 5000 characters"), 400

        submission = ContactSubmission(
            name=name,
            email=email,
            message=message,
        )

        try:
            db.session.add(submission)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Contact submission database error")
            return jsonify(error="Submission could not be saved"), 500

        return jsonify(
            status="received",
            submission_id=submission.id,
        ), 201


    # Serve the existing public HTML/CSS/JS from the same origin as the API.
    public_dir = Path(__file__).resolve().parent.parent / "html" / "web" / "public"

    @app.get("/")
    def serve_home():
        return send_from_directory(public_dir, "index.html")

    @app.get("/<path:filename>")
    def serve_public_page(filename):
        parts = filename.replace(chr(92), "/").split("/")
        if any(
            part.startswith(".")
            or part.lower().endswith((".bak", ".zip", ".py", ".db", ".env"))
            or ".bak." in part.lower()
            or ".before-" in part.lower()
            or "backup" in part.lower()
            for part in parts
        ):
            return jsonify(error="Not found"), 404
        return send_from_directory(public_dir, filename)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
