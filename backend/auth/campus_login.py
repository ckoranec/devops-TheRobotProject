"""
Card 4: Fake campus login and signed identity token.
David Noyes — 2026-11-06

LOCAL SIMULATION ONLY.

Uses the team's existing fake users database and Flask-Bcrypt instance.
Does not create staff sessions, assign roles, or modify the map.

Run tests:
    python -m pytest backend/auth/campus_login.py -v

Run application:
    python backend/auth/campus_login.py
"""

import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

from flask import Flask, render_template_string, request, session
from itsdangerous import URLSafeTimedSerializer

# Reuse the team's database location and shared Flask-Bcrypt instance.
# Password hashing now lives in password_hashing.py.
# Support running this file directly or importing it as a package.
if __package__:
    from .seed_users import DB_FILE
    from .password_hashing import bcrypt
else:
    from seed_users import DB_FILE
    from password_hashing import bcrypt


ISSUER = "maxbytes-fake-campus"
AUDIENCE = "maxbytes-campus-demo"
TOKEN_SALT = "maxbytes-campus-demo-v1"
TOKEN_TTL_SECONDS = 60

PAGE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MaxBytes — Fake Campus Login</title>
    <style>
        body {
            margin: 0;
            padding: 24px;
            font-family: Arial, sans-serif;
            background: #f3f5f7;
            color: #17212b;
        }

        main {
            max-width: 640px;
            margin: 30px auto;
            padding: 28px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        }

        label {
            display: block;
            margin-top: 18px;
            font-weight: bold;
        }

        input, textarea {
            box-sizing: border-box;
            width: 100%;
            margin-top: 8px;
            padding: 12px;
            border: 1px solid #aab5bf;
            border-radius: 6px;
            font-size: 16px;
        }

        button {
            margin-top: 20px;
            padding: 12px 18px;
            border: 0;
            border-radius: 6px;
            background: #075c45;
            color: white;
            font-size: 16px;
            cursor: pointer;
        }

        .notice {
            padding: 12px;
            background: #fff4d6;
            border-radius: 6px;
        }

        .error {
            color: #a01818;
            font-weight: bold;
        }

        .success {
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid #d5dce2;
        }
    </style>
</head>
<body>
    <main>
        <h1>MaxBytes Campus Login</h1>

        <p class="notice">
            <strong>Local simulation — fake accounts only.</strong>
        </p>

        <p>
            This demo issues a signed identity token.
            It does not open the staff map or create a staff session.
        </p>

        {% if error %}
            <p class="error" role="alert">{{ error }}</p>
        {% endif %}

        <form method="post" action="/login">
            <input type="hidden" name="csrf" value="{{ csrf }}">

            <label for="username">Test username</label>
            <input
                id="username"
                name="username"
                required
                maxlength="100"
                autocomplete="username"
            >

            <label for="password">Test password</label>
            <input
                id="password"
                name="password"
                type="password"
                required
                maxlength="256"
                autocomplete="current-password"
            >

            <button type="submit">Sign in to campus demo</button>
        </form>

        {% if token %}
            <section class="success">
                <h2>Signed token created</h2>

                <p>
                    Server processing:
                    {{ elapsed }} milliseconds.
                </p>

                <p>
                    Token acceptance window:
                    {{ ttl }} seconds when checked by the receiver.
                </p>

                <p>
                    Displaying this token is for local testing only.
                    Do not post it in chat, screenshots, or GitHub.
                </p>

                <textarea
                    readonly
                    rows="8"
                    aria-label="Signed demo token"
                >{{ token }}</textarea>

                <p>No staff session has been created.</p>
            </section>
        {% endif %}
    </main>
</body>
</html>
"""


def token_serializer(secret):
    """Create a timestamped signer with a dedicated token purpose."""
    return URLSafeTimedSerializer(
        secret,
        salt=TOKEN_SALT,
        signer_kwargs={"digest_method": hashlib.sha256},
    )


def find_identity(username, password):
    """Verify a fake account without creating or changing database records."""
    database = Path(DB_FILE)

    if not database.is_file():
        raise RuntimeError("Run backend/auth/seed_users.py first.")

    # Read-only mode prevents this app from altering the shared database.
    database_uri = database.resolve().as_uri() + "?mode=ro"

    with sqlite3.connect(database_uri, uri=True) as connection:
        row = connection.execute(
            """
            SELECT id, username, password_hash
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

    if row is None:
        return None

    # Use the team's existing Flask-Bcrypt instance.
    # Never print or store the submitted password.
    if not bcrypt.check_password_hash(row[2], password):
        return None

    return {
        "id": str(row[0]),
        "username": row[1],
    }


def issue_token(serializer, identity):
    """Sign an identity assertion without passwords or staff permissions."""
    return serializer.dumps(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": identity["id"],
            "username": identity["username"],
            "iat": int(time.time()),
            "jti": secrets.token_urlsafe(24),
            "demo": True,
            "amr": ["pwd"],
        }
    )


def create_app(secret, identity_lookup=find_identity):
    """Build the local demo application."""
    if not secret or len(secret) < 32:
        raise RuntimeError(
            "Set CAMPUS_DEMO_SECRET to a random value "
            "of at least 32 characters before starting."
        )

    app = Flask(__name__)

    app.config.update(
        SECRET_KEY=secret,
        MAX_CONTENT_LENGTH=4096,
        SESSION_COOKIE_NAME="maxbytes_campus_demo",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        # Local loopback HTTP only. A deployed app requires HTTPS.
        SESSION_COOKIE_SECURE=False,
    )

    signer = token_serializer(secret)

    @app.before_request
    def local_only():
        """Reject nonlocal requests and unexpected Host headers."""
        if (
            request.remote_addr not in {"127.0.0.1", "::1"}
            or request.host != "127.0.0.1:5051"
        ):
            return "Local demo only.", 403

    @app.after_request
    def protect_response(response):
        """Avoid browser caching of login pages and issued tokens."""
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    def page(error="", token="", elapsed=""):
        """Render the form and optional local demonstration result."""
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)

        return render_template_string(
            PAGE,
            csrf=session["csrf"],
            error=error,
            token=token,
            elapsed=elapsed,
            ttl=TOKEN_TTL_SECONDS,
        )

    @app.get("/")
    def index():
        return page()

    @app.post("/login")
    def login():
        started = time.perf_counter()

        # The form token helps prevent cross-site login submissions.
        expected = session.get("csrf", "")
        supplied = request.form.get("csrf", "")

        if not expected or not secrets.compare_digest(expected, supplied):
            return page(error="Reload the page and try again."), 400

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if (
            not username
            or len(username) > 100
            or not password
            or len(password) > 256
        ):
            return page(error="Login failed."), 401

        try:
            identity = identity_lookup(username, password)
        except (sqlite3.Error, RuntimeError):
            return page(
                error="Demo database unavailable. Check setup."
            ), 503

        if identity is None:
            return page(error="Login failed."), 401

        token = issue_token(signer, identity)

        # This cookie holds form protection only, not staff authorization.
        session.clear()

        elapsed = f"{(time.perf_counter() - started) * 1000:.1f}"

        return page(token=token, elapsed=elapsed)

    return app


# Tests remain in this file to follow the one-file-per-card rule.
# They use fake identities and do not read or modify users.db.


def test_token_contents():
    signer = token_serializer(secrets.token_urlsafe(48))

    token = issue_token(
        signer,
        {"id": "123", "username": "fake_user"},
    )

    data = signer.loads(token, max_age=TOKEN_TTL_SECONDS)

    assert data["iss"] == ISSUER
    assert data["aud"] == AUDIENCE
    assert data["sub"] == "123"
    assert data["username"] == "fake_user"
    assert data["demo"] is True
    assert data["amr"] == ["pwd"]
    assert data["jti"]
    assert "password" not in data
    assert "role" not in data


def test_token_tampering_and_wrong_key():
    import pytest
    from itsdangerous import BadSignature

    signer = token_serializer(secrets.token_urlsafe(48))

    token = issue_token(
        signer,
        {"id": "123", "username": "fake_user"},
    )

    with pytest.raises(BadSignature):
        signer.loads(
            "changed." + token,
            max_age=TOKEN_TTL_SECONDS,
        )

    other_signer = token_serializer(secrets.token_urlsafe(48))

    with pytest.raises(BadSignature):
        other_signer.loads(token, max_age=TOKEN_TTL_SECONDS)


def test_token_expiration(monkeypatch):
    import pytest
    from itsdangerous import SignatureExpired, TimestampSigner

    # Control the signing clock so this test needs no waiting.
    monkeypatch.setattr(
        TimestampSigner,
        "get_timestamp",
        lambda self: 1000,
    )

    signer = token_serializer(secrets.token_urlsafe(48))

    token = issue_token(
        signer,
        {"id": "123", "username": "fake_user"},
    )

    monkeypatch.setattr(
        TimestampSigner,
        "get_timestamp",
        lambda self: 1061,
    )

    with pytest.raises(SignatureExpired):
        signer.loads(token, max_age=TOKEN_TTL_SECONDS)


def test_login_routes():
    def fake_lookup(username, password):
        if (
            username == "fake_user"
            and password == "fake-test-password"
        ):
            return {"id": "123", "username": username}

        return None

    app = create_app(
        secrets.token_urlsafe(48),
        identity_lookup=fake_lookup,
    )

    app.config["TESTING"] = True
    client = app.test_client()
    base = "http://127.0.0.1:5051"

    response = client.get("/", base_url=base)
    assert response.status_code == 200

    # Missing form protection must be rejected.
    response = client.post("/login", base_url=base)
    assert response.status_code == 400

    response = client.get("/", base_url=base)

    match = re.search(
        r'name="csrf" value="([^"]+)"',
        response.get_data(as_text=True),
    )

    assert match is not None
    csrf = match.group(1)

    response = client.post(
        "/login",
        base_url=base,
        data={
            "csrf": csrf,
            "username": "fake_user",
            "password": "wrong",
        },
    )

    assert response.status_code == 401
    assert b"Signed token created" not in response.data

    response = client.post(
        "/login",
        base_url=base,
        data={
            "csrf": csrf,
            "username": "fake_user",
            "password": "fake-test-password",
        },
    )

    assert response.status_code == 200
    assert b"Signed token created" in response.data
    assert response.headers["Cache-Control"] == "no-store"

    response = client.get(
        "/",
        base_url="http://untrusted.example:5051",
    )

    assert response.status_code == 403


if __name__ == "__main__":
    application = create_app(os.environ.get("CAMPUS_DEMO_SECRET"))
    application.run(
        host="127.0.0.1",
        port=5051,
        debug=False,
    )