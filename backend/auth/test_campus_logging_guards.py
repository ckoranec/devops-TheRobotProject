# 2026-11-25 - David Noyes
# Check campus refusal logs using temporary accounts and databases.

import sqlite3
import time

import pytest

from backend.auth import database, mfa
from backend.auth.test_campus_staff_app import (
    BASE,
    PROVIDER,
    begin_campus_mfa,
    campus_token,
    setup,
)


@pytest.mark.parametrize("service", ["staff", "provider"])
@pytest.mark.parametrize("reason", ["host", "address", "size"])
def test_campus_request_guard_is_logged(setup, caplog, service, reason):
    staff, provider, password = setup
    caplog.set_level("INFO")

    if service == "staff":
        client = staff
        base = BASE
        page = "/campus"
        submission = "/auth/campus/callback"
        event = "campus_sso"
    else:
        client = provider
        base = PROVIDER
        page = "/login"
        submission = "/login"
        event = "campus_provider"

    caplog.clear()

    if reason == "host":
        response = client.get(
            base.replace("127.0.0.1", "localhost") + page
        )
        expected_status = 403
        expected_result = "host_refused"

    elif reason == "address":
        response = client.get(
            base + page,
            environ_overrides={"REMOTE_ADDR": "192.0.2.10"},
        )
        expected_status = 403
        expected_result = "local_address_refused"

    else:
        # An active provider form makes it read the submitted body.
        if service == "provider":
            start = staff.get(BASE + "/auth/campus/start")
            page_response = provider.get(start.headers["Location"])
            assert page_response.status_code == 200

        response = client.post(
            base + submission,
            data={"csrf": "x" * 20000},
        )
        expected_status = 413
        expected_result = "request_too_large"

    assert response.status_code == expected_status

    message = (
        f"event={event} | result={expected_result} | campus_id=-"
    )
    assert caplog.messages.count(message) == 1
    assert password not in caplog.text
    assert "result=identity_accepted" not in caplog.text
    assert staff.get(BASE + "/staff").status_code == 403


def test_campus_pending_expiry_is_logged(setup, caplog):
    client = begin_campus_mfa(setup)

    with client.session_transaction(base_url=BASE) as saved:
        saved["pending_started"] = time.time() - mfa.PENDING_SECONDS - 1

    caplog.set_level("INFO")
    caplog.clear()

    response = client.get(BASE + "/campus")

    assert response.status_code == 302
    assert (
        "event=campus_sso | result=pending_mfa_expired | campus_id=-"
        in caplog.messages
    )

    with client.session_transaction(base_url=BASE) as saved:
        assert not saved

    assert client.get(BASE + "/staff").status_code == 403


def test_mapping_database_failure_is_logged(setup, monkeypatch, caplog):
    client, _, password = setup
    token = campus_token(setup)

    def unavailable_mapping(campus_id):
        # This replacement exists only during the test.
        raise sqlite3.OperationalError("Test database unavailable")

    monkeypatch.setattr(
        database,
        "get_staff_id_by_campus_id",
        unavailable_mapping,
    )

    caplog.set_level("INFO")
    caplog.clear()

    response = client.post(
        BASE + "/auth/campus/callback",
        data={"token": token},
    )

    assert response.status_code == 503
    assert (
        "event=campus_sso | result=staff_directory_unavailable"
        " | campus_id=CAMPUS-1001"
        in caplog.messages
    )
    assert "result=identity_accepted" not in caplog.text
    assert password not in caplog.text
    assert token not in caplog.text

    with client.session_transaction(base_url=BASE) as saved:
        assert "pending_mfa_user_id" not in saved
        assert "authenticated_user_id" not in saved
        assert not saved.get("mfa_verified")

    assert client.get(BASE + "/staff").status_code == 403
