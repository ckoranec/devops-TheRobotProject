# 2026-11-18 - David Noyes - Attach campus SSO to the imported shared app.
# Adds a campus entry point without editing Colin's or Shek's source files.
# Run from the repository root: python -m backend.auth.campus_staff_app

import sqlite3
import time
from pathlib import Path

from flask import redirect, render_template_string, request, session, url_for

from backend.auth import database
from backend.auth.app import create_app as create_shared_app
from backend.auth.mfa import PENDING_SECONDS
from campus_sso.campus_provider import read_secret, register_staff_sso


PAGE = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campus sign in with staff MFA</title>
<style>
body {font-family:Arial,sans-serif;background:#eef2f5;color:#172b3a;padding:32px 16px;}
main {max-width:680px;margin:auto;background:white;padding:28px;border-radius:12px;}
p {line-height:1.6;} a {color:#075c45;} .button {display:inline-block;padding:12px 18px;
background:#075c45;color:white;border-radius:6px;text-decoration:none;}
</style></head>
<body><main><h1>Campus sign in with staff MFA</h1>
<p>Local campus simulation using the team's staff login and authenticator verification.</p>
<h2>{{ heading }}</h2><p>{{ message }}</p>
<a class="button" href="/auth/campus/start">Sign in with campus account</a>
<p><a href="/">Use staff username and password instead</a></p>
<p><a href="/staff">Check staff access</a></p>
<form action="/logout" method="post"><button type="submit">Log out</button></form>
</main></body></html>
"""


def check_database_setup():
    # Read-only mode prevents a wrong path from creating an empty users.db.
    database_uri = Path(database.DB_FILE).resolve().as_uri() + "?mode=ro"
    try:
        connection = sqlite3.connect(database_uri, uri=True)
        try:
            for table in ("users", "campus_accounts", "staff_campus_mapping"):
                found = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (table,),
                ).fetchone()
                if found is None:
                    raise RuntimeError("Local database setup is missing table: " + table)
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise RuntimeError("Cannot read the existing users.db. Check local setup.") from error


def register_campus_sso(app):
    """Attach Dave's campus routes to an existing shared Flask application."""
    if app.extensions.get("dave_campus_sso"):
        return app
    check_database_setup()
    app.config["MAX_CONTENT_LENGTH"] = 16384

    @app.before_request
    def check_local_request():
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return "Local demonstration only.", 403
        if request.host != "127.0.0.1:5051":
            return "Use http://127.0.0.1:5051/campus.", 403

        # A new campus attempt must not retain an earlier authenticated session.
        if request.path == "/auth/campus/start":
            session.clear()

        # Expire the pending MFA stage created by this campus adapter.
        started = session.get("pending_started")
        if session.get("pending_mfa_user_id") and started is not None:
            if time.time() - started >= PENDING_SECONDS:
                session.clear()
                return redirect(url_for("campus_home"))

    @app.after_request
    def protect_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/campus")
    def campus_home():
        return render_template_string(
            PAGE,
            heading="Begin campus sign in",
            message="Verify your campus account, then complete staff MFA. Campus identity alone does not open the staff page.",
        )

    def resolve_staff(campus_id):
        # Colin's lookup returns a numeric staff ID or None.
        staff_id = database.get_staff_id_by_campus_id(campus_id)
        if staff_id is None:
            return None
        # Refuse a stale mapping whose staff account no longer exists.
        if database.get_user_by_id(staff_id) is None:
            return None
        return staff_id

    def begin_staff_login(staff_user_id):
        # Match Colin's password-login handoff, without claiming MFA success.
        session.clear()
        session["pending_mfa_user_id"] = staff_user_id
        session["mfa_verified"] = False
        session["pending_started"] = time.time()
        # Shek's route chooses setup for a new user or code entry for an existing user.
        return redirect(url_for("mfa.verify_code_page"))

    def write_event(event, result, campus_id=None):
        # Use Python logging, as the shared MFA module does. Never log tokens/passwords.
        app.logger.info("event=%s | result=%s | campus_id=%s", event, result, campus_id or "-")

    register_staff_sso(app, resolve_staff, begin_staff_login, write_event)

    @app.after_request
    def explain_campus_refusal(response):
        if request.path == "/auth/campus/callback" and response.status_code == 403:
            response.set_data(render_template_string(
                PAGE,
                heading="Staff access refused",
                message="The proof was invalid, expired, or the campus identity had no valid staff mapping. Start a new sign-in attempt.",
            ))
            response.content_type = "text/html; charset=utf-8"
        return response

    app.extensions["dave_campus_sso"] = True
    return app


def create_app():
    # Reuse the team factory; it registers staff and MFA exactly once.
    read_secret("FLASK_SECRET_KEY")
    read_secret("CAMPUS_SSO_SIGNING_KEY")
    check_database_setup()
    app = create_shared_app()
    return register_campus_sso(app)


if __name__ == "__main__":
    # Use the shared application's account_activity.log configuration.
    create_app().run(host="127.0.0.1", port=5051, debug=False)
