# 2026-11-20 - David Noyes
# Verify campus hook isolation and shared pending-MFA rejection.

import sqlite3
import time

import pyotp
import pytest

from backend.auth import mfa
from backend.auth.test_campus_staff_app import (
    BASE,
    setup,
    begin_campus_mfa,
)


def test_localhost_password_login_reaches_shared_mfa(setup):
    client, _, password = setup
    base = "http://localhost:5051"
    assert client.get(base + "/").status_code == 200

    response = client.post(
        base + "/login",
        data={"username": "fixture_staff", "password": password},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/verify-code"

    response = client.get(base + "/verify-code", follow_redirects=True)
    assert response.status_code == 200
    assert "Set Up Two-Factor Authentication" in response.text


@pytest.mark.parametrize(
    "path", ["/campus", "/campus/continue", "/auth/campus/start"]
)
def test_campus_host_guard_remains_local(setup, path):
    assert setup[0].get("http://localhost:5051" + path).status_code == 403


def test_expired_pending_session_is_cleared_on_campus_route(setup):
    client = begin_campus_mfa(setup)
    with client.session_transaction(base_url=BASE) as saved:
        saved["pending_started"] = time.time() - mfa.PENDING_SECONDS - 1

    response = client.get(BASE + "/campus")
    assert response.status_code == 302
    assert response.headers["Location"] == "/campus"
    with client.session_transaction(base_url=BASE) as saved:
        assert not saved


def test_campus_timeout_does_not_intercept_shared_routes(setup):
    client = begin_campus_mfa(setup)
    with client.session_transaction(base_url=BASE) as saved:
        saved["pending_started"] = time.time() - mfa.PENDING_SECONDS - 1

    assert client.get(BASE + "/").status_code == 200
    with client.session_transaction(base_url=BASE) as saved:
        assert saved["pending_mfa_user_id"] == 7


def test_campus_headers_and_body_limit_do_not_change_shared_app(setup):
    client = setup[0]
    assert client.application.config["MAX_CONTENT_LENGTH"] is None
    assert client.get(BASE + "/campus").headers["Cache-Control"] == "no-store"
    assert "X-Frame-Options" not in client.get(BASE + "/").headers

    response = client.post(
        BASE + "/auth/campus/callback",
        data={"token": "x" * 17000},
    )
    assert response.status_code == 413


def test_shared_mfa_refuses_valid_code_after_pending_expiry(setup):
    client = begin_campus_mfa(setup)
    secret = pyotp.random_base32()

    with sqlite3.connect(mfa.TOTP_DB_PATH) as connection:
        connection.execute(
            "INSERT INTO totp_secrets "
            "(user_id, totp_secret, confirmed) VALUES (?, ?, 1)",
            (7, secret),
        )

    with client.session_transaction(base_url=BASE) as saved:
        saved["pending_started"] = time.time() - mfa.PENDING_SECONDS - 1

    client.post(
        BASE + "/verify-code",
        data={"code": pyotp.TOTP(secret).now()},
    )
    assert client.get(BASE + "/staff").status_code == 403