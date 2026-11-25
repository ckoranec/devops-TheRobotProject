# 2026-11-25 - David Noyes
# Verify campus outcome logs with temporary accounts and databases.

import os
import re
import secrets
import sqlite3
import time

import pytest

from backend.auth import database
from backend.auth.test_campus_staff_app import (
    BASE,
    PROVIDER,
    campus_token,
    setup,
)
from campus_sso import campus_provider
from campus_sso.provider_sessions import COOKIE_NAME, IDLE_SECONDS
from campus_sso.test_provider_sessions import (
    new_request,
    password_login,
)


def assert_logged(caplog, event, result, campus_id="-"):
    expected = (
        f"event={event} | result={result} | campus_id={campus_id}"
    )
    assert expected in caplog.messages


def assert_no_staff_access(staff):
    assert staff.get(BASE + "/staff").status_code == 403

    with staff.session_transaction(base_url=BASE) as saved:
        assert "authenticated_user_id" not in saved
        assert not saved.get("mfa_verified")


@pytest.mark.parametrize(
    "case, expected_result, expected_status",
    [
        ("expired_form", "request_expired", 400),
        ("missing_state", "invalid_request", 400),
        ("bad_csrf", "form_refused", 400),
        ("empty_username", "invalid_credentials", 400),
        ("empty_password", "invalid_credentials", 400),
        ("directory_failure", "directory_unavailable", 503),
        ("session_capacity", "session_capacity", 503),
        ("account_disappeared", "session_revoked", 401),
    ],
)
def test_provider_form_outcomes_are_logged(
    setup, monkeypatch, caplog, case, expected_result, expected_status
):
    staff, provider, password = setup

    start = staff.get(BASE + "/auth/campus/start")
    page = provider.get(start.headers["Location"])
    assert page.status_code == 200

    csrf = re.search(
        r'name="csrf" value="([^"]+)"',
        page.text,
    ).group(1)

    form = {
        "username": "campus_staff",
        "password": password,
        "csrf": csrf,
    }

    if case == "expired_form":
        with provider.session_transaction(base_url=PROVIDER) as saved:
            saved["started"] = (
                time.time() - campus_provider.REQUEST_TTL - 1
            )

    elif case == "missing_state":
        with provider.session_transaction(base_url=PROVIDER) as saved:
            saved.pop("sso_state", None)

    elif case == "bad_csrf":
        form["csrf"] = "invalid"

    elif case == "empty_username":
        form["username"] = ""

    elif case == "empty_password":
        form["password"] = ""

    elif case == "directory_failure":
        def unavailable_directory(*args):
            raise sqlite3.OperationalError("Temporary test failure")

        monkeypatch.setattr(
            campus_provider,
            "find_campus_identity",
            unavailable_directory,
        )

    elif case == "session_capacity":
        store = provider.application.extensions["campus_provider_sessions"]
        store.capacity = 0

    elif case == "account_disappeared":
        def missing_identity(*args):
            return None

        monkeypatch.setattr(
            campus_provider,
            "current_identity",
            missing_identity,
        )

    caplog.set_level("INFO")
    caplog.clear()

    response = provider.post(PROVIDER + "/login", data=form)

    assert response.status_code == expected_status
    assert 'name="token"' not in response.text
    assert_logged(caplog, "campus_provider", expected_result)
    assert password not in caplog.text
    assert csrf not in caplog.text
    assert_no_staff_access(staff)


@pytest.mark.parametrize(
    "case, expected_result",
    [
        ("missing_token", "invalid_token"),
        ("wrong_audience", "invalid_claims"),
        ("wrong_state", "invalid_claims"),
        ("missing_request", "invalid_or_replayed_request"),
    ],
)
def test_receiver_refusal_outcomes_are_logged(
    setup, caplog, case, expected_result
):
    staff, _, password = setup
    original_token = campus_token(setup)
    submitted_token = original_token

    if case == "missing_token":
        submitted_token = ""

    elif case in ("wrong_audience", "wrong_state"):
        signer = campus_provider.token_serializer(
            os.environ["CAMPUS_SSO_SIGNING_KEY"]
        )
        claims = signer.loads(original_token)

        if case == "wrong_audience":
            claims["aud"] = "different-test-site"
        else:
            claims["state"] = secrets.token_urlsafe(32)

        submitted_token = signer.dumps(claims)

    elif case == "missing_request":
        with staff.session_transaction(base_url=BASE) as saved:
            saved.pop("campus_sso_state", None)

    caplog.set_level("INFO")
    caplog.clear()

    response = staff.post(
        BASE + "/auth/campus/callback",
        data={"token": submitted_token},
    )

    assert response.status_code == 403
    assert_logged(caplog, "campus_sso", expected_result)
    assert "result=identity_accepted" not in caplog.text
    assert password not in caplog.text
    assert original_token not in caplog.text

    if submitted_token:
        assert submitted_token not in caplog.text

    with staff.session_transaction(base_url=BASE) as saved:
        assert "pending_mfa_user_id" not in saved

    assert_no_staff_access(staff)


@pytest.mark.parametrize(
    "case, expected_result",
    [
        ("expired", "session_expired"),
        ("unknown_cookie", "session_invalid"),
        ("deleted_account", "session_revoked"),
    ],
)
def test_remembered_session_refusals_are_logged(
    setup, caplog, case, expected_result
):
    staff, provider, password = setup
    assert password_login(setup).status_code == 200

    cookie = provider.get_cookie(COOKIE_NAME, domain="127.0.0.1")
    store = provider.application.extensions["campus_provider_sessions"]

    if case == "expired":
        store.records[cookie.value]["seen"] = (
            store.clock() - IDLE_SECONDS - 1
        )

    elif case == "unknown_cookie":
        provider.set_cookie(
            COOKIE_NAME,
            secrets.token_urlsafe(32),
            domain="127.0.0.1",
        )

    else:
        # Only the fixture's temporary database is changed.
        with sqlite3.connect(database.DB_FILE) as connection:
            connection.execute(
                "DELETE FROM campus_accounts WHERE campus_id = ?",
                ("CAMPUS-1001",),
            )

    caplog.set_level("INFO")
    caplog.clear()

    response = new_request(setup)

    assert response.status_code == 200
    assert 'name="password"' in response.text
    assert 'name="token"' not in response.text
    assert_logged(caplog, "campus_provider", expected_result)
    assert password not in caplog.text
    assert cookie.value not in caplog.text
    assert_no_staff_access(staff)


def test_provider_logout_outcomes_are_logged(setup, caplog):
    staff, provider, password = setup
    assert password_login(setup).status_code == 200
    cookie = provider.get_cookie(COOKIE_NAME, domain="127.0.0.1")

    caplog.set_level("INFO")
    caplog.clear()

    refused = provider.post(
        PROVIDER + "/logout",
        data={"csrf": "invalid"},
    )

    assert refused.status_code == 403
    assert_logged(caplog, "campus_provider", "logout_refused")

    page = provider.get(PROVIDER + "/logout")
    csrf = re.search(
        r'name="csrf" value="([^"]+)"',
        page.text,
    ).group(1)

    accepted = provider.post(
        PROVIDER + "/logout",
        data={"csrf": csrf},
    )

    assert accepted.status_code == 200
    assert_logged(caplog, "campus_provider", "logout")
    assert provider.get_cookie(
        COOKIE_NAME, domain="127.0.0.1"
    ) is None
    assert 'name="password"' in new_request(setup).text
    assert password not in caplog.text
    assert cookie.value not in caplog.text
    assert csrf not in caplog.text
    assert_no_staff_access(staff)