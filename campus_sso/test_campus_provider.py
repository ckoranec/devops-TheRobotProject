# 2026-11-18 - David Noyes - Provider tests moved here for pytest discovery.
import re
import secrets
import time

from itsdangerous import BadData
from campus_sso.campus_provider import (
    CALLBACK_URL, PROVIDER_URL, TOKEN_TTL, check_token,
    create_provider, make_token, token_serializer,
)


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


