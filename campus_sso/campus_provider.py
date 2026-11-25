# 2026-11-25 - David Noyes
# Campus provider, remembered login, signed proof, and refusal logging.
# Run from the project root: python -m campus_sso.campus_provider

import logging
import re
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlencode

from flask import (
    Flask,
    make_response,
    redirect,
    render_template_string,
    request,
    session,
)
from itsdangerous import BadData, SignatureExpired

from backend.auth.campus_directory import find_campus_identity
from backend.auth.campus_login import token_serializer
from campus_sso.config import load_provider_config, read_secret
from campus_sso.provider_sessions import (
    COOKIE_NAME,
    ProviderSessions,
    current_identity,
)


ISSUER = "maxbytes-fake-campus-v2"
AUDIENCE = "maxbytes-staff-demo-v2"
TOKEN_TTL = 60
REQUEST_TTL = 300

PROVIDER_URL = "http://127.0.0.1:5052/login"
CALLBACK_URL = "http://127.0.0.1:5051/auth/campus/callback"

STATE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
CAMPUS_ID_PATTERN = re.compile(r"^CAMPUS-[0-9]+$")


LOGIN_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Staff Login - Campus Account</title>
</head>
<body>
    <main>
        <h1>Staff Login - Campus Account</h1>
        <p><strong>Fake university login - local simulation only.</strong></p>
        <p>The university verifies your identity.
           The staff site decides whether you have access.</p>
        {% if error %}
            <p role="alert">{{ error }}</p>
        {% endif %}
        <form method="post">
            <input type="hidden" name="csrf" value="{{ csrf }}">
            <p>
                <label>
                    Campus username
                    <input name="username" required maxlength="100"
                           autocomplete="username">
                </label>
            </p>
            <p>
                <label>
                    Campus password
                    <input type="password" name="password" required
                           maxlength="256" autocomplete="current-password">
                </label>
            </p>
            <button type="submit">Sign in with campus account</button>
        </form>
    </main>
</body>
</html>
"""


RETURN_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Returning to staff site</title>
</head>
<body>
    <p>Campus identity verified. Returning to the staff site...</p>
    <form id="return-form" method="post" action="{{ callback }}">
        <input type="hidden" name="token" value="{{ token }}">
        <button type="submit">Continue to staff site</button>
    </form>
    <script>
        document.getElementById("return-form").submit();
    </script>
</body>
</html>
"""


def make_token(signer, identity, state):
    # Prove campus identity without claiming staff permission or completed MFA.
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": identity["campus_id"],
        "affiliation": identity["affiliation"],
        "iat": now,
        "exp": now + TOKEN_TTL,
        "state": state,
        "jti": secrets.token_urlsafe(24),
        "demo": True,
        "amr": ["pwd"],
    }
    return signer.dumps(claims)


def check_token(signer, token, expected_state):
    claims = signer.loads(token, max_age=TOKEN_TTL)

    if not isinstance(claims, dict):
        raise ValueError("Invalid claims")

    if claims.get("iss") != ISSUER or claims.get("aud") != AUDIENCE:
        raise ValueError("Wrong issuer or audience")

    if claims.get("demo") is not True or claims.get("amr") != ["pwd"]:
        raise ValueError("Wrong authentication context")

    issued = claims.get("iat")
    expiry = claims.get("exp")
    now = int(time.time())

    if type(issued) is not int or type(expiry) is not int:
        raise ValueError("Invalid times")

    if issued > now or expiry <= issued or expiry - issued > TOKEN_TTL:
        raise ValueError("Invalid times")

    if now >= expiry:
        raise ValueError("Expired token")

    subject = claims.get("sub")
    if not isinstance(subject, str):
        raise ValueError("Invalid campus identity")

    if not CAMPUS_ID_PATTERN.fullmatch(subject):
        raise ValueError("Invalid campus identity")

    if claims.get("affiliation") not in ("staff", "student"):
        raise ValueError("Invalid affiliation")

    # The proof must belong to this browser's original login request.
    returned_state = claims.get("state")

    if not isinstance(returned_state, str):
        raise ValueError("Wrong login request")

    if not isinstance(expected_state, str):
        raise ValueError("Wrong login request")

    if not STATE_PATTERN.fullmatch(returned_state):
        raise ValueError("Wrong login request")

    if not STATE_PATTERN.fullmatch(expected_state):
        raise ValueError("Wrong login request")

    if not secrets.compare_digest(returned_state, expected_state):
        raise ValueError("Wrong login request")

    if not isinstance(claims.get("jti"), str) or not claims["jti"]:
        raise ValueError("Missing token identifier")

    return claims


def create_provider(database_path=None, session_store=None):
    # Tests supply a temporary database; normal startup uses the campus database.
    app = Flask(__name__)
    app.config.update(load_provider_config())
    app.config["SESSION_COOKIE_NAME"] = "maxbytes_fake_campus"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 8192

    signer = token_serializer(read_secret("CAMPUS_SSO_SIGNING_KEY"))
    store = session_store if session_store is not None else ProviderSessions()
    app.extensions["campus_provider_sessions"] = store

    def record(result, campus_id=None):
        # Never include passwords, cookies, signing keys, or tokens.
        app.logger.info(
            "event=campus_provider | result=%s | campus_id=%s",
            result,
            campus_id or "-",
        )

    @app.errorhandler(413)
    def oversized_request(error):
        record("request_too_large")
        return "Campus request is too large.", 413

    def return_proof(identity, state):
        # A remembered login receives fresh proof for each new request.
        session.clear()
        return make_response(
            render_template_string(
                RETURN_HTML,
                token=make_token(signer, identity, state),
                callback=CALLBACK_URL,
            )
        )

    @app.errorhandler(sqlite3.Error)
    def unavailable_directory(error):
        record("directory_unavailable")
        return "Campus directory unavailable. Please try again later.", 503

    @app.get("/logout")
    def logout_form():
        session["logout_csrf"] = secrets.token_urlsafe(32)
        return render_template_string(
            """
            <h1>Sign out of campus provider</h1>
            <p>This ends remembered campus login.
               Staff-site logout is separate.</p>
            <form method="post">
                <input type="hidden" name="csrf" value="{{ csrf }}">
                <button>Sign out of campus provider</button>
            </form>
            """,
            csrf=session["logout_csrf"],
        )

    @app.post("/logout")
    def logout_provider():
        supplied = request.form.get("csrf", "")
        expected = session.get("logout_csrf", "")

        if (
            not STATE_PATTERN.fullmatch(supplied)
            or not expected
            or not secrets.compare_digest(supplied, expected)
        ):
            record("logout_refused")
            return "Invalid logout form.", 403

        store.revoke(request.cookies.get(COOKIE_NAME))
        session.clear()
        record("logout")

        response = make_response(
            "<p>Campus provider signed out.</p>"
            '<a href="http://127.0.0.1:5051/campus">'
            "Return to staff campus entry</a>"
        )
        response.delete_cookie(
            COOKIE_NAME,
            path="/",
            httponly=True,
            samesite="Lax",
        )
        return response

    @app.before_request
    def local_only():
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            record("local_address_refused")
            return "Local simulation only.", 403

        if request.host != "127.0.0.1:5052":
            record("host_refused")
            return "Local simulation only.", 403

    @app.after_request
    def protect(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/")
    def index():
        return (
            "<h1>Staff Login - Campus Provider</h1>"
            "<p>Local simulation is running.</p>"
            "<p>Start from the staff site's campus sign-in button.</p>"
            "<p>This page does not create a staff session.</p>"
            '<a href="/logout">Sign out of campus provider</a>'
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            state = request.args.get("state", "")
            if not STATE_PATTERN.fullmatch(state):
                record("invalid_request")
                return "Start from the staff site's sign-in button.", 400

            remembered = request.cookies.get(COOKIE_NAME)
            if remembered:
                identity, outcome = store.lookup(remembered, database_path)
                record(outcome, identity["campus_id"] if identity else None)

                if identity is not None:
                    return return_proof(identity, state)

            session.clear()
            session["sso_state"] = state
            session["csrf"] = secrets.token_urlsafe(32)
            session["started"] = time.time()

        if time.time() - session.get("started", 0) > REQUEST_TTL:
            record("request_expired")
            return "Login request expired. Start again at the staff site.", 400

        state = session.get("sso_state", "")
        if not STATE_PATTERN.fullmatch(state):
            record("invalid_request")
            return "Invalid login request. Start again.", 400

        error = ""
        status = 200

        if request.method == "POST":
            expected = session.get("csrf", "")
            supplied = request.form.get("csrf", "")

            if not STATE_PATTERN.fullmatch(supplied):
                record("form_refused")
                return "Invalid form. Start again.", 400

            if not expected or not secrets.compare_digest(expected, supplied):
                record("form_refused")
                return "Invalid form. Start again.", 400

            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if not username or len(username) > 100:
                record("invalid_credentials")
                return "Login refused.", 400

            if not password or len(password) > 256:
                record("invalid_credentials")
                return "Login refused.", 400

            identity = find_campus_identity(
                username,
                password,
                database_path,
            )

            if identity is not None:
                current = current_identity(identity["campus_id"], database_path)
                if current is None:
                    record("session_revoked")
                    return "Login refused.", 401

                try:
                    remembered = store.create(
                        identity,
                        current[1],
                        request.cookies.get(COOKIE_NAME),
                    )
                except RuntimeError:
                    record("session_capacity")
                    return "Please try again later.", 503

                response = return_proof(identity, state)

                # Local HTTP demonstration; production requires HTTPS.
                response.set_cookie(
                    COOKIE_NAME,
                    remembered,
                    httponly=True,
                    samesite="Lax",
                    secure=False,
                    path="/",
                )
                record("password_accepted", identity["campus_id"])
                return response

            record("invalid_credentials")
            error = "Login failed."
            status = 401

        response = make_response(
            render_template_string(
                LOGIN_HTML,
                csrf=session.get("csrf", ""),
                error=error,
            ),
            status,
        )

        # Remove an invalid remembered-login cookie when showing a new form.
        response.delete_cookie(
            COOKIE_NAME,
            path="/",
            httponly=True,
            samesite="Lax",
        )
        return response

    return app


def register_staff_sso(
    app,
    resolve_staff,
    begin_staff_login,
    write_event,
    *,
    signing_key=None,
):
    key = read_secret(
        "CAMPUS_SSO_SIGNING_KEY",
        None if signing_key is None else {
            "CAMPUS_SSO_SIGNING_KEY": signing_key
        },
    )
    signer = token_serializer(key)
    pending = {}

    def record(result, campus_id=None):
        write_event(
            event="campus_sso",
            result=result,
            campus_id=campus_id,
        )

    def refuse(result, campus_id=None):
        record(result, campus_id)
        return "Campus sign-in refused. Start again.", 403

    @app.get("/auth/campus/start")
    def campus_start():
        now = time.time()

        for old_state, deadline in list(pending.items()):
            if deadline <= now:
                pending.pop(old_state, None)

        if len(pending) >= 1000:
            record("request_capacity")
            return "Please try again later.", 503

        previous = session.pop("campus_sso_state", None)
        pending.pop(previous, None)

        state = secrets.token_urlsafe(32)
        session["campus_sso_state"] = state
        pending[state] = now + REQUEST_TTL

        record("started")
        return redirect(PROVIDER_URL + "?" + urlencode({"state": state}))

    @app.post("/auth/campus/callback")
    def campus_callback():
        # Consume the request so the same proof cannot be accepted twice.
        state = session.pop("campus_sso_state", "")
        deadline = pending.pop(state, 0)

        if not state or deadline <= time.time():
            return refuse("invalid_or_replayed_request")

        token = request.form.get("token", "")
        if not token or len(token) > 8192:
            return refuse("invalid_token")

        try:
            claims = check_token(signer, token, state)
        except SignatureExpired:
            return refuse("expired_token")
        except BadData:
            return refuse("invalid_signature")
        except ValueError as error:
            if str(error) == "Expired token":
                return refuse("expired_token")
            return refuse("invalid_claims")

        try:
            staff = resolve_staff(claims["sub"])
        except sqlite3.Error:
            record("staff_directory_unavailable", claims["sub"])
            return "Staff directory unavailable. Please try again later.", 503

        if staff is None:
            return refuse("no_staff_role", claims["sub"])

        # Identity acceptance begins shared login; it does not complete MFA.
        record("identity_accepted", claims["sub"])
        return begin_staff_login(staff)

    return app


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(
                Path(__file__).with_name("provider_activity.log"),
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )
    create_provider().run(host="127.0.0.1", port=5052, debug=False)