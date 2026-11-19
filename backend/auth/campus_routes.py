# 2026-11-18 - David Noyes - Campus receiver blueprint and session navigation.
# Adds a campus entry point without editing Colin's or Shek's source files.
# Registered by Dave's launcher now, or by the shared factory after owner integration.

import secrets
import sqlite3
import time
from pathlib import Path

from flask import abort, Blueprint, current_app, redirect, render_template_string, request, session, url_for

from backend.auth import database
from backend.auth.mfa import PENDING_SECONDS
from backend.auth.staff_login import begin_staff_login
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
{% if verified %}
<a class="button" href="{{ url_for('campus.continue_staff') }}">Continue to staff area</a>
<p>Your existing session has completed MFA. Starting a new sign-in requires MFA again.</p>
{% endif %}
<a class="button" href="/auth/campus/start">Sign in with campus account</a>
<p><a href="/">Use staff username and password instead</a></p>
<p><a href="/staff">Check staff access</a></p>
<form action="{{ url_for('campus.campus_logout') }}" method="post">
<input type="hidden" name="csrf" value="{{ logout_csrf }}">
<button type="submit">Log out of campus session</button></form>
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


def create_campus_blueprint():
    """Build Dave's routes without importing or constructing the shared app."""
    bp = Blueprint("campus", __name__)

    def verified_session():
        staff_id = session.get("authenticated_user_id")
        return bool(session.get("mfa_verified") is True and staff_id
                    and database.get_user_by_id(staff_id) is not None)

    def render_page(heading, message):
        if "campus_logout_csrf" not in session:
            session["campus_logout_csrf"] = secrets.token_urlsafe(32)
        return render_template_string(
            PAGE, heading=heading, message=message,
            verified=verified_session(), logout_csrf=session["campus_logout_csrf"],
        )

    @bp.before_request
    def check_local_request():
        # Blueprint-local: never intercept staff or MFA endpoints.
        request.max_content_length = 16384
        if request.content_length is not None and request.content_length > 16384:
            abort(413)
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return "Local demonstration only.", 403
        if request.host != "127.0.0.1:5051":
            return "Use http://127.0.0.1:5051/campus.", 403

        # A new campus attempt must not retain an earlier authenticated session.
        if request.path == "/auth/campus/start":
            session.clear()

        # Honor a pending timestamp if the shared login supplies one.
        # Colin's current handoff does not yet set it; see README_CAMPUS_SSO.md.
        started = session.get("pending_started")
        if session.get("pending_mfa_user_id") and started is not None:
            if time.time() - started >= PENDING_SECONDS:
                session.clear()
                return redirect(url_for("campus.campus_home"))

    @bp.after_request
    def protect_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @bp.get("/campus")
    def campus_home():
        return render_page(
            "Campus sign in",
            "Continue an already verified session, or begin a fresh campus sign-in with MFA.",
        )

    @bp.get("/campus/continue")
    def continue_staff():
        # Reuse only existing authentication; Colin's route remains the final gate.
        if not verified_session():
            return redirect(url_for("campus.campus_home"))
        return redirect(url_for("staff.staff_page"))

    @bp.post("/campus/logout")
    def campus_logout():
        expected = session.get("campus_logout_csrf", "")
        supplied = request.form.get("csrf", "")
        if not expected or not secrets.compare_digest(expected, supplied):
            return "Invalid logout request. Return to /campus and try again.", 403
        session.clear()
        return redirect(url_for("campus.campus_home"))

    def resolve_staff(campus_id):
        # Colin's lookup returns a numeric staff ID or None.
        staff_id = database.get_staff_id_by_campus_id(campus_id)
        if staff_id is None:
            return None
        # Refuse a stale mapping whose staff account no longer exists.
        if database.get_user_by_id(staff_id) is None:
            return None
        return staff_id

    def write_event(event, result, campus_id=None):
        # Use Python logging, as the shared MFA module does. Never log tokens/passwords.
        current_app.logger.info("event=%s | result=%s | campus_id=%s", event, result, campus_id or "-")

    register_staff_sso(bp, resolve_staff, begin_staff_login, write_event)

    @bp.after_request
    def explain_campus_refusal(response):
        if request.path == "/auth/campus/callback" and response.status_code == 403:
            response.set_data(render_page(
                heading="Staff access refused",
                message="The proof was invalid, expired, or the campus identity had no valid staff mapping. Start a new sign-in attempt.",
            ))
            response.content_type = "text/html; charset=utf-8"
        return response

    return bp


def register_campus_sso(app):
    """Owner-facing interface: call once inside the shared app factory."""
    if app.extensions.get("dave_campus_sso"):
        return app
    check_database_setup()
    read_secret("CAMPUS_SSO_SIGNING_KEY")
    app.register_blueprint(create_campus_blueprint())
    app.extensions["dave_campus_sso"] = True
    return app
