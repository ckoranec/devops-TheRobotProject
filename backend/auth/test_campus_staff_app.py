# 2026-11-17 - Real campus -> shared MFA -> shared staff route integration tests.
# All accounts, passwords, signing keys, and databases are disposable test data.
# 2026-11-17 - David Noyes - Verify acceptance/refusal logging without secrets.

import re
import secrets
import sqlite3
import time
from html import unescape

import pyotp
import pytest

from backend.auth import database, mfa, app as shared_app
from backend.auth.campus_directory import seed_campus_accounts
from backend.auth.campus_staff_app import create_app, register_campus_sso
from backend.auth.password_hashing import hash_password
from campus_sso.campus_provider import create_provider

BASE = "http://127.0.0.1:5051"
PROVIDER = "http://127.0.0.1:5052"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    # Use temporary databases so tests do not change your real accounts.
    path = tmp_path / "users.db"
    monkeypatch.setattr(database, "DB_FILE", str(path))
    monkeypatch.setattr(shared_app, "DB_FILE", str(path))
    monkeypatch.setattr(mfa, "TOTP_DB_PATH", str(tmp_path / "totp.db"))
    password = secrets.token_urlsafe(24)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE users "
            "(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)"
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (7, "fixture_staff", hash_password(password)),
        )

    seed_campus_accounts(path, password, password)
    database.create_staff_campus_mapping()

    with database.get_db_connection() as connection:
        connection.execute(
            "INSERT INTO staff_campus_mapping VALUES (?, ?)",
            ("CAMPUS-1001", 7),
        )

    for name in (
        "CAMPUS_SSO_SIGNING_KEY",
        "CAMPUS_IDP_COOKIE_SECRET",
        "FLASK_SECRET_KEY",
    ):
        monkeypatch.setenv(name, secrets.token_urlsafe(48))

    app = shared_app.create_app()
    app.config["TESTING"] = True

    provider = create_provider(path)
    provider.config["TESTING"] = True

    return app.test_client(), provider.test_client(), password


def campus_token(setup, username="campus_staff", password=None):
    # Follow the campus login flow and extract its signed test token.
    client, provider, saved_password = setup
    # Credential-specific tests use a fresh provider browser; remembered SSO has its own tests.
    provider = provider.application.test_client()
    start = client.get(BASE + "/auth/campus/start")
    assert start.status_code == 302

    page = provider.get(start.headers["Location"])
    csrf = re.search(
        r'name="csrf" value="([^"]+)"',
        page.text,
    ).group(1)

    result = provider.post(
        PROVIDER + "/login",
        data={
            "username": username,
            "password": saved_password if password is None else password,
            "csrf": csrf,
        },
    )
    assert result.status_code == 200

    return unescape(
        re.search(r'name="token" value="([^"]+)"', result.text).group(1)
    )


def begin_campus_mfa(setup):
    client = setup[0]
    token = campus_token(setup)
    response = client.post(
        BASE + "/auth/campus/callback",
        data={"token": token},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/verify-code"
    return client


def test_campus_staff_completes_real_mfa_and_logout(setup):
    client = begin_campus_mfa(setup)

    with client.session_transaction(base_url=BASE) as saved:
        assert saved["pending_mfa_user_id"] == 7
        assert saved["mfa_verified"] is False
        assert "authenticated_user_id" not in saved

    assert client.get(BASE + "/staff").status_code == 403

    page = client.get(BASE + "/verify-code", follow_redirects=True)
    assert "Set Up Two-Factor Authentication" in page.text

    record = mfa.get_totp_record(7)
    code = pyotp.TOTP(record[0]).now()
    result = client.post(
        BASE + "/setup-2fa",
        data={"code": code},
        follow_redirects=True,
    )
    assert result.status_code == 200
    assert "Welcome to the GMU Robot Project staff area!" in result.text

    with client.session_transaction(base_url=BASE) as saved:
        assert saved["authenticated_user_id"] == 7
        assert saved["mfa_verified"] is True
        assert "pending_mfa_user_id" not in saved

    assert client.post(BASE + "/logout").status_code == 302
    assert client.get(BASE + "/staff").status_code == 403


def test_student_refused_before_mfa(setup):
    client = setup[0]
    token = campus_token(setup, "campus_student")
    result = client.post(
        BASE + "/auth/campus/callback",
        data={"token": token},
    )
    assert result.status_code == 403
    assert "Staff access refused" in result.text

    with client.session_transaction(base_url=BASE) as saved:
        assert "pending_mfa_user_id" not in saved
        assert not saved.get("mfa_verified")

    assert client.get(BASE + "/staff").status_code == 403


def test_existing_authenticator_uses_verify_route(setup):
    secret = pyotp.random_base32()

    with sqlite3.connect(mfa.TOTP_DB_PATH) as connection:
        connection.execute(
            "INSERT INTO totp_secrets "
            "(user_id,totp_secret,confirmed) VALUES (?,?,1)",
            (7, secret),
        )

    client = begin_campus_mfa(setup)
    page = client.get(BASE + "/verify-code")
    assert "Two-Factor Authentication" in page.text
    assert "Set Up Two-Factor" not in page.text

    used_code = pyotp.TOTP(secret).now()
    result = client.post(
        BASE + "/verify-code",
        data={"code": used_code},
        follow_redirects=True,
    )
    assert "Welcome to the GMU Robot Project staff area!" in result.text

    # A new login cannot reuse the same successful time-step code.
    begin_campus_mfa(setup)
    result = client.post(
        BASE + "/verify-code",
        data={"code": used_code},
    )
    assert "Invalid code" in result.text
    assert client.get(BASE + "/staff").status_code == 403


def test_five_wrong_codes_lock_setup(setup):
    client = begin_campus_mfa(setup)
    client.get(BASE + "/verify-code", follow_redirects=True)

    for attempt in range(5):
        response = client.post(
            BASE + "/setup-2fa",
            data={"code": "bad"},
        )

    assert "Locked out for 1 minute" in response.text
    record = mfa.get_totp_record(7)
    assert record[1] == 5

    valid_code = pyotp.TOTP(record[0]).now()
    response = client.post(
        BASE + "/setup-2fa",
        data={"code": valid_code},
    )
    assert "Too many failed attempts" in response.text
    assert client.get(BASE + "/staff").status_code == 403


def test_pending_campus_mfa_expires(setup):
    # Shared MFA now owns expiry rejection and returns its timeout page.
    client = begin_campus_mfa(setup)

    with client.session_transaction(base_url=BASE) as saved:
        saved["pending_started"] = time.time() - mfa.PENDING_SECONDS - 1

    response = client.get(BASE + "/verify-code")
    assert response.status_code == 401
    assert "Your sign-in timed out" in response.text
    assert response.headers["Cache-Control"] == "no-store"

    with client.session_transaction(base_url=BASE) as saved:
        assert "pending_mfa_user_id" not in saved
        assert "authenticated_user_id" not in saved
        assert not saved.get("mfa_verified")

    assert client.get(BASE + "/staff").status_code == 403


def test_shared_password_login_still_reaches_mfa(setup):
    client, _, password = setup
    response = client.post(
        BASE + "/login",
        data={"username": "fixture_staff", "password": password},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/verify-code"
    assert client.get(BASE + "/staff").status_code == 403

    page = client.get(BASE + "/verify-code", follow_redirects=True)
    assert "Set Up Two-Factor Authentication" in page.text


def test_changed_and_replayed_proof_refused(setup):
    client = setup[0]
    token = campus_token(setup)
    changed = ("B" if token[0] == "A" else "A") + token[1:]

    response = client.post(
        BASE + "/auth/campus/callback",
        data={"token": changed},
    )
    assert response.status_code == 403

    token = campus_token(setup)
    response = client.post(
        BASE + "/auth/campus/callback",
        data={"token": token},
    )
    assert response.status_code == 302

    response = client.post(
        BASE + "/auth/campus/callback",
        data={"token": token},
    )
    assert response.status_code == 403
    assert client.get(BASE + "/staff").status_code == 403


def test_new_campus_attempt_clears_previous_staff_session(setup):
    client = setup[0]

    with client.session_transaction(base_url=BASE) as saved:
        saved["authenticated_user_id"] = 7
        saved["mfa_verified"] = True

    token = campus_token(setup, "campus_student")
    response = client.post(
        BASE + "/auth/campus/callback",
        data={"token": token},
    )
    assert response.status_code == 403
    assert client.get(BASE + "/staff").status_code == 403


def test_missing_mapping_table_fails_at_startup(setup):
    with database.get_db_connection() as connection:
        connection.execute("DROP TABLE staff_campus_mapping")

    with pytest.raises(RuntimeError, match="staff_campus_mapping"):
        create_app()


def test_local_host_required(setup):
    client = setup[0]
    assert client.get("http://localhost:5051/campus").status_code == 403
    assert client.get(BASE + "/campus").status_code == 200


# 2026-11-17 - David Noyes
# Check the real application logger for acceptance and refusal.
@pytest.mark.parametrize(
    "username, campus_id, expected_status, expected_result",
    [
        ("campus_staff", "CAMPUS-1001", 302, "identity_accepted"),
        ("campus_student", "CAMPUS-2001", 403, "no_staff_role"),
    ],
)
def test_campus_outcome_is_logged(
    setup, caplog, username, campus_id, expected_status, expected_result
):
    # Reuse isolated test clients and a disposable account password.
    client, _, password = setup

    # Capture INFO messages from the integrated receiving application.
    with caplog.at_level("INFO", logger=client.application.logger.name):
        token = campus_token(setup, username)
        response = client.post(
            BASE + "/auth/campus/callback",
            data={"token": token},
        )

    # Confirm the expected acceptance or refusal.
    assert response.status_code == expected_status

    # Confirm the outcome and campus identity were logged.
    expected_message = (
        f"event=campus_sso | result={expected_result} | campus_id={campus_id}"
    )
    assert expected_message in caplog.messages

    # Confirm the password and signed proof did not enter captured logs.
    assert password not in caplog.text
    assert token not in caplog.text


# 2026-11-18 - David Noyes - Confirm reuse of the real shared application.
def test_shared_blueprints_registered_once(setup):
    app = setup[0].application
    assert "staff" in app.blueprints
    assert "mfa" in app.blueprints
    before = list(app.url_map.iter_rules())
    assert register_campus_sso(app) is app
    assert list(app.url_map.iter_rules()) == before


def test_provider_posts_to_shared_callback(setup):
    from campus_sso.campus_provider import CALLBACK_URL
    assert CALLBACK_URL == BASE + "/auth/campus/callback"
    client = begin_campus_mfa(setup)
    assert client.get(BASE + "/staff").status_code == 403


def test_old_receiver_port_is_refused(setup):
    assert setup[0].get("http://127.0.0.1:5000/campus").status_code == 403
