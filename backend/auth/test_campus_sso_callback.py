# 2026-11-13 — David Noyes — Card 4 staff callback tests.
# These substitutes test the callback; they do not implement real staff login.

import secrets
import time
from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask

from campus_sso.campus_login import (
    make_token,
    register_staff_sso,
    token_serializer,
)


@pytest.fixture
def callback_setup(monkeypatch):
    # Give every test its own application, signing key, and recorded results.
    signing_key = secrets.token_urlsafe(48)
    monkeypatch.setenv("CAMPUS_SSO_SIGNING_KEY", signing_key)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = secrets.token_urlsafe(48)

    events = []
    handoffs = []
    lookups = []

    def fake_resolve_staff(campus_id):
        # TEST SUBSTITUTE: only one campus identity has a staff mapping.
        lookups.append(campus_id)

        if campus_id == "CAMPUS-1001":
            return {"id": 7, "username": "test_staff"}

        return None

    def fake_begin_staff_login(staff):
        # TEST SUBSTITUTE: record the handoff without granting a session.
        handoffs.append(staff)
        return "TEST ONLY: shared MFA handoff reached.", 200

    def fake_write_event(event, result, campus_id=None):
        # TEST SUBSTITUTE: collect events in memory instead of the shared log.
        events.append(
            {
                "event": event,
                "result": result,
                "campus_id": campus_id,
            }
        )

    # Register the real callback with substitutes for its three dependencies.
    register_staff_sso(
        app,
        fake_resolve_staff,
        fake_begin_staff_login,
        fake_write_event,
    )

    return {
        "client": app.test_client(),
        "signer": token_serializer(signing_key),
        "events": events,
        "handoffs": handoffs,
        "lookups": lookups,
    }


def start_login_and_make_token(
    setup,
    campus_id="CAMPUS-1001",
    affiliation="staff",
):
    # Start a real callback request and extract its random request identifier.
    response = setup["client"].get("/auth/campus/start")
    assert response.status_code == 302

    redirect_url = response.headers["Location"]
    query = parse_qs(urlparse(redirect_url).query)
    state = query["state"][0]

    # Build signed proof using the provider's real token-generation function.
    identity = {
        "campus_id": campus_id,
        "affiliation": affiliation,
    }

    return make_token(setup["signer"], identity, state)


def test_callback_hands_mapped_staff_to_shared_login(callback_setup):
    # A valid mapped identity must reach the supplied staff-login function.
    setup = callback_setup
    token = start_login_and_make_token(setup)

    response = setup["client"].post(
        "/auth/campus/callback",
        data={"token": token},
    )

    assert response.status_code == 200
    assert setup["lookups"] == ["CAMPUS-1001"]
    assert setup["handoffs"] == [{"id": 7, "username": "test_staff"}]
    assert setup["events"][-1] == {
        "event": "campus_sso",
        "result": "identity_accepted",
        "campus_id": "CAMPUS-1001",
    }

    # The substitute must not pretend that MFA or authentication is complete.
    with setup["client"].session_transaction() as saved_session:
        assert not saved_session.get("mfa_verified")
        assert "authenticated_user_id" not in saved_session


@pytest.mark.parametrize(
    "campus_id, affiliation",
    [
        ("CAMPUS-2001", "student"),
        ("CAMPUS-9999", "staff"),
    ],
)
def test_callback_refuses_identity_without_staff_mapping(
    callback_setup,
    campus_id,
    affiliation,
):
    # Both students and unmapped staff identities must be refused.
    setup = callback_setup
    token = start_login_and_make_token(setup, campus_id, affiliation)

    response = setup["client"].post(
        "/auth/campus/callback",
        data={"token": token},
    )

    assert response.status_code == 403
    assert setup["lookups"] == [campus_id]
    assert setup["handoffs"] == []
    assert setup["events"][-1] == {
        "event": "campus_sso",
        "result": "no_staff_role",
        "campus_id": campus_id,
    }


def test_callback_refuses_changed_token(callback_setup):
    # Change one signed character and verify refusal before staff lookup.
    setup = callback_setup
    token = start_login_and_make_token(setup)

    replacement = "A" if token[0] != "A" else "B"
    changed_token = replacement + token[1:]

    response = setup["client"].post(
        "/auth/campus/callback",
        data={"token": changed_token},
    )

    assert response.status_code == 403
    assert setup["lookups"] == []
    assert setup["handoffs"] == []
    assert setup["events"][-1]["result"] == "invalid_signature"


def test_callback_refuses_expired_token(callback_setup):
    # Create correctly signed proof whose explicit expiry is already past.
    setup = callback_setup
    token = start_login_and_make_token(setup)
    claims = setup["signer"].loads(token)

    claims["iat"] = int(time.time()) - 120
    claims["exp"] = claims["iat"] + 60
    expired_token = setup["signer"].dumps(claims)

    response = setup["client"].post(
        "/auth/campus/callback",
        data={"token": expired_token},
    )

    assert response.status_code == 403
    assert setup["lookups"] == []
    assert setup["handoffs"] == []
    assert setup["events"][-1]["result"] == "expired_token"


def test_callback_refuses_wrong_request_state(callback_setup):
    # Validly signed proof must still match this browser's login request.
    setup = callback_setup
    token = start_login_and_make_token(setup)
    claims = setup["signer"].loads(token)

    claims["state"] = secrets.token_urlsafe(32)
    wrong_state_token = setup["signer"].dumps(claims)

    response = setup["client"].post(
        "/auth/campus/callback",
        data={"token": wrong_state_token},
    )

    assert response.status_code == 403
    assert setup["lookups"] == []
    assert setup["handoffs"] == []
    assert setup["events"][-1]["result"] == "invalid_claims"


def test_callback_refuses_replayed_request(callback_setup):
    # Reusing an already accepted callback must not start another login.
    setup = callback_setup
    token = start_login_and_make_token(setup)

    first_response = setup["client"].post(
        "/auth/campus/callback",
        data={"token": token},
    )
    second_response = setup["client"].post(
        "/auth/campus/callback",
        data={"token": token},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 403
    assert len(setup["handoffs"]) == 1
    assert setup["events"][-1]["result"] == "invalid_or_replayed_request"