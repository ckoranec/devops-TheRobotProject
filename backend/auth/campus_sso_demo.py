# 2026-11-16 ? David Noyes ? Update references to the renamed campus provider.
# 2026-11-14 — David Noyes — Card 4 local browser demonstration.
# TEMPORARY until Card 1 login integration: no real staff sessions or MFA.

import logging
import secrets
import tempfile
from pathlib import Path

from flask import Flask, render_template_string, request

from campus_sso.campus_provider import (
    read_secret,
    register_staff_sso,
)


# Use one page layout for the demonstration start, success, and refusal pages.
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
            Real staff sessions and MFA are not connected.
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
    # Keep this app's browser cookie separate from the campus and staff apps.
    app = Flask(__name__)
    app.secret_key = read_secret("CAMPUS_DEMO_COOKIE_SECRET")
    app.config["SESSION_COOKIE_NAME"] = "maxbytes_campus_receiver_demo"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 16384

    # Store demo events outside the repository, separate from the shared log.
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
        # Accept requests only through this demonstration's loopback address.
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return "Local demonstration only.", 403
        if request.host != "127.0.0.1:5000":
            return "Use http://127.0.0.1:5000.", 403

    @app.after_request
    def protect(response):
        # Prevent authentication pages from being cached or embedded elsewhere.
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/")
    def home():
        # Start the real provider flow without displaying or accepting tokens.
        return render_template_string(
            PAGE,
            heading="Begin the campus sign-in demonstration",
            message=(
                "The campus application checks your campus account. "
                "This receiver checks the signed proof returned by that app."
            ),
        )

    def demo_resolve_staff(campus_id):
        # TEMPORARY: one fixed demo mapping; no real database mapping is changed.
        if campus_id == "CAMPUS-1001":
            return {"campus_id": campus_id}
        return None

    def demo_begin_staff_login(staff):
        # TEMPORARY: show the handoff point without setting authentication flags.
        return render_template_string(
            PAGE,
            heading="Campus identity verified",
            message=(
                f"{staff['campus_id']} was accepted by the demo mapping. "
                "The next integration step is the shared MFA handoff."
            ),
        )

    def demo_write_event(event, result, campus_id=None):
        # Record callback outcomes without storing passwords or signed tokens.
        logger.info(
            "event=%s | result=%s | campus_id=%s",
            event,
            result,
            campus_id or "-",
        )

    # Reuse the real start and callback routes with the three demo substitutes.
    register_staff_sso(
        app,
        demo_resolve_staff,
        demo_begin_staff_login,
        demo_write_event,
    )

    @app.after_request
    def explain_refusal(response):
        # Keep callback refusals visibly labeled as part of this demonstration.
        if request.path == "/auth/campus/callback" and response.status_code == 403:
            response.set_data(
                render_template_string(
                    PAGE,
                    heading="Staff access refused",
                    message=(
                        "The proof was invalid, expired, or had no demo staff "
                        "mapping. The demo log records the refusal reason."
                    ),
                )
            )
            response.content_type = "text/html; charset=utf-8"
        return response

    return app


def test_demo_callback_and_log(tmp_path, monkeypatch):
    # Exercise the receiver with signed fixtures and a disposable log file.
    from urllib.parse import parse_qs, urlparse

    from campus_sso.campus_provider import make_token, token_serializer

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

    try:
        # Confirm that staff reaches the handoff and the student is refused.
        for campus_id, affiliation, expected_status in [
            ("CAMPUS-1001", "staff", 200),
            ("CAMPUS-2001", "student", 403),
        ]:
            client = app.test_client()
            start = client.get("http://127.0.0.1:5000/auth/campus/start")
            assert start.status_code == 302
            state = parse_qs(urlparse(start.headers["Location"]).query)["state"][0]

            token = make_token(
                signer,
                {"campus_id": campus_id, "affiliation": affiliation},
                state,
            )
            response = client.post(
                "http://127.0.0.1:5000/auth/campus/callback",
                data={"token": token},
            )

            assert response.status_code == expected_status
            assert b"No authenticated staff session" in response.data

            with client.session_transaction() as saved_session:
                assert not saved_session.get("mfa_verified")
                assert "authenticated_user_id" not in saved_session

        # Check that both outcomes were logged without including the token.
        log_text = log_path.read_text(encoding="utf-8")
        assert "result=identity_accepted | campus_id=CAMPUS-1001" in log_text
        assert "result=no_staff_role | campus_id=CAMPUS-2001" in log_text
        assert token not in log_text

    finally:
        # Close test log handles so Windows can remove the temporary directory.
        logger = app.extensions["campus_demo_logger"]
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


# Launch only when explicitly run; importing this file does not start a server.
if __name__ == "__main__":
    create_demo().run(host="127.0.0.1", port=5000, debug=False)