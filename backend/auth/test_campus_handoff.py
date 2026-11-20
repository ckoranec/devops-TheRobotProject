# 2026-11-20 - David Noyes
# Verify campus and password login use Colin's actual shared handoff.
# Existing sessions include activity timestamps required by his idle check.

import time

from backend.auth import campus_routes, staff_login
from backend.auth.test_campus_staff_app import (
    BASE,
    setup,
    begin_campus_mfa,
)


def test_campus_imports_colins_actual_function():
    # Campus must import the shared function rather than maintain a copy.
    assert campus_routes.begin_staff_login is staff_login.begin_staff_login


def seed_active_session(client):
    # Represent an existing, active staff session before starting a new login.
    with client.session_transaction(base_url=BASE) as saved:
        saved["authenticated_user_id"] = 7
        saved["mfa_verified"] = True
        saved["last_activity"] = time.time()
        saved["old_session_marker"] = "must disappear"


def read_pending_session(client, started_before, finished_after):
    with client.session_transaction(base_url=BASE) as saved:
        state = dict(saved)

    assert state["pending_mfa_user_id"] == 7
    assert state["mfa_verified"] is False

    # The shared handoff must clear the previous authenticated session.
    assert "authenticated_user_id" not in state
    assert "old_session_marker" not in state
    assert "last_activity" not in state

    # Each login must start its own pending-MFA timer.
    pending_started = state.pop("pending_started")
    assert isinstance(pending_started, (int, float))
    assert started_before <= pending_started <= finished_after

    # Return the remaining fields for comparison between the two login paths.
    return state


def test_password_and_campus_use_same_pending_session(setup):
    client, _, password = setup
    seed_active_session(client)

    campus_started = time.time()
    begin_campus_mfa(setup)
    campus_finished = time.time()

    campus_state = read_pending_session(
        client, campus_started, campus_finished
    )
    assert client.get(BASE + "/staff").status_code == 403

    password_client = client.application.test_client()
    seed_active_session(password_client)

    password_started = time.time()
    response = password_client.post(
        BASE + "/login",
        data={
            "username": "fixture_staff",
            "password": password,
        },
    )
    password_finished = time.time()

    assert response.status_code == 302
    assert response.headers["Location"] == "/verify-code"

    password_state = read_pending_session(
        password_client, password_started, password_finished
    )

    # Authentication state must agree; timestamps were checked independently.
    assert password_state == campus_state
    assert password_client.get(BASE + "/staff").status_code == 403