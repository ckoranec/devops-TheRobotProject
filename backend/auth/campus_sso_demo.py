# 2026-11-16 — David Noyes — Use the shared staff mapping in the SSO demo.
# TEMPORARY until Card 1 integration: MFA handoff and logging remain demo-only.

import logging
import secrets
import tempfile
from pathlib import Path

from flask import Flask, render_template_string, request

from backend.auth import database
from campus_sso.campus_provider import read_secret, register_staff_sso


# Keep the demonstration's limits visible on every result page.
PAGE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Staff Login — SSO Demonstration</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #eef2f5;
            color: #172b3a;
            margin: 0;
            padding: 32px 16px;
        }
        main {
            max-width: 680px;
            margin: auto;
            background: white;
            padding: 28px;
            border-radius: 12px;
        }
        .notice {
            background: #fff3cd;
            padding: 16px;
            line-height: 1.5;
        }
        .button {
            display: inline-block;
            background: #075c45;
            color: white;
            padding: 12px 18px;
            border-radius: 6px;
            text-decoration: none;
        }
        p { line-height: 1.6; }
    </style>
</head>
<body>
    <main>
        <h1>Staff Login — SSO Demonstration</h1>
        <p class="notice">
            <strong>Temporary integration demonstration.</strong>
            The shared database mapping is connected.
            Real staff sessions and MFA are not connected.
            Logging is demonstration-only.
        </p>
        <h2>{{ heading }}</h2>
        <p>{{ message }}</p>
        <p>No authenticated staff session has been created.</p>
        <a class="button" href="/auth/campus/start">
            Sign in with campus account
        </a>
        <p>Campus provider: port 5052. Demo receiver: port 5000.</p>
    </main>
</body>
</html>
"""


def create_demo(log_path=None):
    # Use a distinct cookie so the demo does not replace other apps' cookies.
    app = Flask(__name__)
    app.secret_key = read_secret("CAMPUS_DEMO_COOKIE_SECRET")
    app.config["SESSION_COOKIE_NAME"] = "maxbytes_campus_receiver_demo"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 16384

    # Keep demonstration events separate from the shared authentication log.
    if log_path is None:
        log_path = Path(tempfile.gettempdir()) / "maxbytes_campus_sso_demo.log"

    logger = logging.Logger("campus_sso_demo", level=logging.INFO)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s | DEMO ONLY | %(message)s")
    )
    logger.addHandler(handler)
    app.extensions["campus_demo_logger"] = logger

    @app.before_request
    def local_only():
        # Restrict this development receiver to its expected local address.
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return "Local demonstration only.", 403
        if request.host != "127.0.0.1:5000":
            return "Use http://127.0.0.1:5000.", 403

    @app.after_request
    def protect(response):
        # Prevent caching and embedding of authentication responses.
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/")
    def home():
        # Begin campus authentication before checking the shared staff mapping.
        return render_template_string(
            PAGE,
            heading="Begin the campus sign-in demonstration",
            message=(
                "The campus provider checks your campus account. "
                "This receiver verifies its proof and uses the shared "
                "database lookup to find a staff mapping."
            ),
        )

    def demo_begin_staff_login(staff_user_id):
        # TEMPORARY: accept the real numeric ID without creating a staff session.
        return render_template_string(
            PAGE,
            heading="Campus identity verified",
            message=(
                f"The shared mapping returned staff user ID {staff_user_id}. "
                "The next integration step is the shared MFA handoff."
            ),
        )

    def demo_write_event(event, result, campus_id=None):
        # TEMPORARY: record callback outcomes without passwords or tokens.
        logger.info(
            "event=%s | result=%s | campus_id=%s",
            event,
            result,
            campus_id or "-",
        )

    # Supply Colin's actual lookup directly; no hardcoded campus mapping remains.
    register_staff_sso(
        app,
        resolve_staff=database.get_staff_id_by_campus_id,
        begin_staff_login=demo_begin_staff_login,
        write_event=demo_write_event,
    )

    @app.after_request
    def explain_refusal(response):
        # Preserve the refusal status while displaying the demo's explanation.
        if request.path == "/auth/campus/callback" and response.status_code == 403:
            response.set_data(
                render_template_string(
                    PAGE,
                    heading="Staff access refused",
                    message=(
                        "The proof was invalid, expired, or the campus ID "
                        "had no staff mapping. The demo log records the reason."
                    ),
                )
            )
            response.content_type = "text/html; charset=utf-8"
        return response

    return app


def test_demo_callback_and_log(tmp_path, monkeypatch):
    # Redirect the real shared functions to a disposable database for this test.
    import sqlite3
    from urllib.parse import parse_qs, urlparse

    from backend.auth.campus_directory import seed_campus_accounts
    from backend.auth.password_hashing import hash_password
    from campus_sso.campus_provider import make_token, token_serializer

    database_path = tmp_path / "staff_mapping_test.db"
    monkeypatch.setattr(database, "DB_FILE", str(database_path))

    # Create the staff fixture only in the disposable database.
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (7, "test_staff", hash_password("Staff-Fixture-Only!")),
        )
        connection.commit()
    finally:
        connection.close()

    # Use the real campus seeder and Colin's real mapping-table setup.
    seed_campus_accounts(
        database_path,
        "Campus-Staff-Fixture!",
        "Campus-Student-Fixture!",
    )
    database.create_staff_campus_mapping()

    connection = database.get_db_connection()
    try:
        connection.execute(
            """
            INSERT INTO staff_campus_mapping (campus_id, staff_user_id)
            VALUES (?, ?)
            """,
            ("CAMPUS-1001", 7),
        )
        connection.commit()
    finally:
        connection.close()

    # Supply random test secrets and a temporary log instead of live settings.
    signing_key = secrets.token_urlsafe(48)
    monkeypatch.setenv("CAMPUS_SSO_SIGNING_KEY", signing_key)
    monkeypatch.setenv(
        "CAMPUS_DEMO_COOKIE_SECRET",
        secrets.token_urlsafe(48),
    )

    log_path = tmp_path / "demo.log"
    app = create_demo(log_path)
    app.config["TESTING"] = True
    signer = token_serializer(signing_key)
    issued_tokens = []

    def submit_identity(campus_id, affiliation):
        # Exercise the real start and callback routes with signed test proof.
        client = app.test_client()
        start = client.get("http://127.0.0.1:5000/auth/campus/start")
        assert start.status_code == 302
        state = parse_qs(urlparse(start.headers["Location"]).query)["state"][0]

        token = make_token(
            signer,
            {"campus_id": campus_id, "affiliation": affiliation},
            state,
        )
        issued_tokens.append(token)

        response = client.post(
            "http://127.0.0.1:5000/auth/campus/callback",
            data={"token": token},
        )

        # The demo must never mark MFA or staff authentication as complete.
        with client.session_transaction() as saved_session:
            assert not saved_session.get("mfa_verified")
            assert "authenticated_user_id" not in saved_session

        return response

    try:
        # A mapped campus ID must hand the database's numeric staff ID onward.
        accepted = submit_identity("CAMPUS-1001", "staff")
        assert accepted.status_code == 200
        assert b"staff user ID 7" in accepted.data

        # Student and staff affiliations without mappings must both be refused.
        student = submit_identity("CAMPUS-2001", "student")
        unmapped_staff = submit_identity("CAMPUS-9999", "staff")
        assert student.status_code == 403
        assert unmapped_staff.status_code == 403

        # Removing the temporary mapping must immediately remove acceptance.
        connection = database.get_db_connection()
        try:
            connection.execute(
                "DELETE FROM staff_campus_mapping WHERE campus_id = ?",
                ("CAMPUS-1001",),
            )
            connection.commit()
        finally:
            connection.close()

        refused_after_removal = submit_identity("CAMPUS-1001", "staff")
        assert refused_after_removal.status_code == 403

        # Verify acceptance and refusal events without storing signed tokens.
        log_text = log_path.read_text(encoding="utf-8")
        assert "result=identity_accepted | campus_id=CAMPUS-1001" in log_text
        assert "result=no_staff_role | campus_id=CAMPUS-2001" in log_text
        assert "result=no_staff_role | campus_id=CAMPUS-9999" in log_text
        assert "result=no_staff_role | campus_id=CAMPUS-1001" in log_text

        for token in issued_tokens:
            assert token not in log_text

    finally:
        # Release log handles so Windows can clean up the temporary test files.
        logger = app.extensions["campus_demo_logger"]
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


# Start only when explicitly launched; importing the module starts no server.
if __name__ == "__main__":
    create_demo().run(host="127.0.0.1", port=5000, debug=False)