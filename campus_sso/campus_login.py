# 2026-11-13 — David Noyes — Card 4 simulated campus identity provider.
# Run from the project root: python -m campus_sso.campus_login

# Import web tools, token validation, and the existing campus database lookup.
import os
import re
import secrets
import time
from urllib.parse import urlencode

from flask import Flask, redirect, render_template_string, request, session
from itsdangerous import BadData, SignatureExpired

from backend.auth.campus_login import token_serializer
from backend.auth.campus_directory import find_campus_identity


# Define the local applications and the maximum lifetimes of login requests.
ISSUER = "maxbytes-fake-campus-v2"
AUDIENCE = "maxbytes-staff-demo-v2"
TOKEN_TTL = 60
REQUEST_TTL = 300
PROVIDER_URL = "http://127.0.0.1:5052/login"
CALLBACK_URL = "http://127.0.0.1:5000/auth/campus/callback"
STATE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
CAMPUS_ID_PATTERN = re.compile(r"^CAMPUS-[0-9]+$")


# Display the fake university login used when entering the staff site.
LOGIN_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Staff Login — Campus Account</title>
</head>
<body>
    <main>
        <h1>Staff Login — Campus Account</h1>
        <p><strong>Fake university login — local simulation only.</strong></p>
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


# Send signed proof to the fixed staff callback in a POST body, not a URL.
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


def read_secret(name):
    # Require an environment secret without displaying its value.
    value = os.environ.get(name, "")
    if len(value) < 32:
        raise RuntimeError(
            f"Set {name} to a random value of at least 32 characters."
        )
    return value


def make_token(signer, identity, state):
    # Sign permanent campus identity without claiming staff authorization or MFA.
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
    # Verify the signature and require this simulation's issuer and audience.
    claims = signer.loads(token, max_age=TOKEN_TTL)
    if not isinstance(claims, dict):
        raise ValueError("Invalid claims")
    if claims.get("iss") != ISSUER or claims.get("aud") != AUDIENCE:
        raise ValueError("Wrong issuer or audience")
    if claims.get("demo") is not True or claims.get("amr") != ["pwd"]:
        raise ValueError("Wrong authentication context")

    # Refuse malformed, future-dated, excessive-lifetime, or expired claims.
    issued = claims.get("iat")
    expiry = claims.get("exp")
    now = int(time.time())
    if type(issued) is not int or type(expiry) is not int:
        raise ValueError("Invalid times")
    if issued > now or expiry <= issued or expiry - issued > TOKEN_TTL:
        raise ValueError("Invalid times")
    if now >= expiry:
        raise ValueError("Expired token")

    # Validate campus identity fields without deciding staff-site permissions.
    subject = claims.get("sub")
    if not isinstance(subject, str):
        raise ValueError("Invalid campus identity")
    if not CAMPUS_ID_PATTERN.fullmatch(subject):
        raise ValueError("Invalid campus identity")
    if claims.get("affiliation") not in ("staff", "student"):
        raise ValueError("Invalid affiliation")

    # Bind the proof to the original request using validated ASCII identifiers.
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


def create_provider(database_path=None):
    # Use the real campus database normally; tests can supply a temporary path.
    app = Flask(__name__)
    app.secret_key = read_secret("CAMPUS_IDP_COOKIE_SECRET")
    app.config["SESSION_COOKIE_NAME"] = "maxbytes_fake_campus"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 8192
    signer = token_serializer(read_secret("CAMPUS_SSO_SIGNING_KEY"))

    # Restrict this development application to its expected local address.
    @app.before_request
    def local_only():
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return "Local simulation only.", 403
        if request.host != "127.0.0.1:5052":
            return "Local simulation only.", 403

    # Prevent caching or framing of authentication responses.
    @app.after_request
    def protect(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    # Explain why real SSO starts at the staff application.
    @app.get("/")
    def index():
        return (
            "<h1>Staff Login — Campus Provider</h1>"
            "<p>Local simulation is running.</p>"
            "<p>Start from the staff site's campus sign-in button.</p>"
            "<p>This page does not create a staff session.</p>"
        )

    # Create the login form and check credentials against campus_accounts only.
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            state = request.args.get("state", "")
            if not STATE_PATTERN.fullmatch(state):
                return "Start from the staff site's sign-in button.", 400
            session.clear()
            session["sso_state"] = state
            session["csrf"] = secrets.token_urlsafe(32)
            session["started"] = time.time()

        # Require an active, unexpired provider form.
        if time.time() - session.get("started", 0) > REQUEST_TTL:
            return "Login request expired. Start again at the staff site.", 400
        state = session.get("sso_state", "")
        if not STATE_PATTERN.fullmatch(state):
            return "Invalid login request. Start again.", 400

        error = ""
        status = 200

        # Check the form's browser binding before processing its credentials.
        if request.method == "POST":
            expected = session.get("csrf", "")
            supplied = request.form.get("csrf", "")
            if not STATE_PATTERN.fullmatch(supplied):
                return "Invalid form. Start again.", 400
            if not expected or not secrets.compare_digest(expected, supplied):
                return "Invalid form. Start again.", 400

            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if not username or len(username) > 100:
                return "Login refused.", 400
            if not password or len(password) > 256:
                return "Login refused.", 400

            # Reuse the read-only campus lookup instead of the staff lookup.
            identity = find_campus_identity(
                username, password, database_path
            )
            if identity is not None:
                token = make_token(signer, identity, state)
                session.clear()
                return render_template_string(
                    RETURN_HTML, token=token, callback=CALLBACK_URL
                )

            error = "Login failed."
            status = 401

        return render_template_string(
            LOGIN_HTML, csrf=session.get("csrf", ""), error=error
        ), status

    return app


def register_staff_sso(app, resolve_staff, begin_staff_login, write_event):
    # Require shared staff functions; pending requests serve one local process.
    signer = token_serializer(read_secret("CAMPUS_SSO_SIGNING_KEY"))
    pending = {}

    def record(result, campus_id=None):
        # Send outcomes to the supplied logger without passwords or tokens.
        write_event(event="campus_sso", result=result, campus_id=campus_id)

    def refuse(result, campus_id=None):
        # Log the reason but display a generic refusal to the browser.
        record(result, campus_id)
        return "Campus sign-in refused. Start again.", 403

    @app.get("/auth/campus/start")
    def campus_start():
        # Remove expired requests and replace this browser's previous attempt.
        now = time.time()
        for old_state, deadline in list(pending.items()):
            if deadline <= now:
                pending.pop(old_state, None)
        if len(pending) >= 1000:
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
        # Consume the original request so it cannot be accepted a second time.
        state = session.pop("campus_sso_state", "")
        deadline = pending.pop(state, 0)
        if not state or deadline <= time.time():
            return refuse("invalid_or_replayed_request")

        token = request.form.get("token", "")
        if not token or len(token) > 8192:
            return refuse("invalid_token")

        # Verify signed proof before asking the shared staff lookup for access.
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

        staff = resolve_staff(claims["sub"])
        if staff is None:
            return refuse("no_staff_role", claims["sub"])

        # Hand off to Card 1; identity acceptance does not mean MFA is complete.
        record("identity_accepted", claims["sub"])
        return begin_staff_login(staff)

    return app


def test_signed_token():
    # Both campus affiliations produce identity proof, without staff roles.
    signer = token_serializer(secrets.token_urlsafe(48))
    state = secrets.token_urlsafe(32)
    for campus_id, affiliation in [
        ("CAMPUS-1001", "staff"),
        ("CAMPUS-2001", "student"),
    ]:
        identity = {"campus_id": campus_id, "affiliation": affiliation}
        token = make_token(signer, identity, state)
        claims = check_token(signer, token, state)
        assert claims["sub"] == campus_id
        assert claims["affiliation"] == affiliation
        assert "password" not in claims
        assert "password_hash" not in claims
        assert "role" not in claims


def test_changed_token():
    # Alter one token character and require signature validation to reject it.
    import pytest

    signer = token_serializer(secrets.token_urlsafe(48))
    state = secrets.token_urlsafe(32)
    identity = {"campus_id": "CAMPUS-1001", "affiliation": "staff"}
    token = make_token(signer, identity, state)
    replacement = "A"
    if token[0] == "A":
        replacement = "B"
    changed = replacement + token[1:]

    with pytest.raises(BadData):
        check_token(signer, changed, state)


def test_expired_token():
    # Sign an already-expired test fixture without waiting for a real timeout.
    import pytest

    signer = token_serializer(secrets.token_urlsafe(48))
    state = secrets.token_urlsafe(32)
    identity = {"campus_id": "CAMPUS-1001", "affiliation": "staff"}
    claims = signer.loads(make_token(signer, identity, state))
    claims["iat"] = int(time.time()) - 61
    claims["exp"] = claims["iat"] + TOKEN_TTL
    expired = signer.dumps(claims)

    with pytest.raises(ValueError, match="Expired token"):
        check_token(signer, expired, state)


def test_provider_uses_campus_database(tmp_path, monkeypatch):
    # Build isolated staff and campus tables without opening the real users.db.
    import sqlite3
    from html import unescape

    from backend.auth.campus_directory import seed_campus_accounts
    from backend.auth.password_hashing import hash_password

    database_path = tmp_path / "provider_test.db"
    password = "Provider-Test-Only!"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "CREATE TABLE users (username TEXT, password_hash TEXT)"
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?)",
            ("staff_test", hash_password(password)),
        )
        connection.commit()
    finally:
        connection.close()

    seed_campus_accounts(database_path, password, password)
    signing_key = secrets.token_urlsafe(48)
    monkeypatch.setenv("CAMPUS_SSO_SIGNING_KEY", signing_key)
    monkeypatch.setenv("CAMPUS_IDP_COOKIE_SECRET", secrets.token_urlsafe(48))
    app = create_provider(database_path)
    app.config["TESTING"] = True
    signer = token_serializer(signing_key)

    # Submit forms through Flask, checking both success and credential refusal.
    cases = [
        ("campus_staff", password, "CAMPUS-1001", "staff"),
        ("campus_student", password, "CAMPUS-2001", "student"),
        ("staff_test", password, None, None),
        ("campus_staff", "wrong-password", None, None),
    ]
    for username, candidate, campus_id, affiliation in cases:
        client = app.test_client()
        state = secrets.token_urlsafe(32)
        page = client.get(
            PROVIDER_URL, query_string={"state": state}
        )
        assert page.status_code == 200
        csrf = re.search(
            r'name="csrf" value="([^"]+)"',
            page.get_data(as_text=True),
        ).group(1)
        response = client.post(
            PROVIDER_URL,
            data={"username": username, "password": candidate, "csrf": csrf},
        )
        html = response.get_data(as_text=True)

        if campus_id is None:
            assert response.status_code == 401
            assert "Login failed." in html
            assert 'name="token"' not in html
        else:
            assert response.status_code == 200
            assert f'action="{CALLBACK_URL}"' in html
            token = unescape(
                re.search(r'name="token" value="([^"]+)"', html).group(1)
            )
            claims = check_token(signer, token, state)
            assert claims["sub"] == campus_id
            assert claims["affiliation"] == affiliation


# Start only when explicitly launched, using the existing local campus database.
if __name__ == "__main__":
    create_provider().run(host="127.0.0.1", port=5052, debug=False)