# 2026-11-18 - David Noyes
# Demonstrate token refusals through the integrated shared application.
# Uses temporary test accounts, databases, and keys; never logs tokens.

import os
import time

import pytest

from backend.auth.test_campus_staff_app import BASE, campus_token, setup
from campus_sso.campus_provider import TOKEN_TTL, token_serializer


@pytest.mark.parametrize(
    "case, expected_result",
    [
        ("changed", "invalid_signature"),
        ("expired", "expired_token"),
    ],
)
def test_integrated_token_refusal_is_logged(
    setup, caplog, case, expected_result
):
    client, _, password = setup
    token = campus_token(setup)

    if case == "changed":
        # Alter exactly one character without creating a new signature.
        replacement = "A" if token[0] != "A" else "B"
        refused_token = replacement + token[1:]
    else:
        # Sign expired proof using only this test's temporary signing key.
        # This tests expiry rejection independently of signature rejection.
        signer = token_serializer(os.environ["CAMPUS_SSO_SIGNING_KEY"])
        claims = signer.loads(token)
        claims["iat"] = int(time.time()) - TOKEN_TTL - 5
        claims["exp"] = claims["iat"] + TOKEN_TTL
        refused_token = signer.dumps(claims)

    caplog.clear()
    with caplog.at_level("INFO", logger=client.application.logger.name):
        response = client.post(
            BASE + "/auth/campus/callback",
            data={"token": refused_token},
        )

    # Check the integrated callback and its visible refusal page.
    assert response.status_code == 403
    assert "Staff access refused" in response.text
    assert client.get(BASE + "/staff").status_code == 403

    # Refused proof must not create pending MFA or authenticated access.
    with client.session_transaction(base_url=BASE) as saved:
        assert "pending_mfa_user_id" not in saved
        assert "authenticated_user_id" not in saved
        assert not saved.get("mfa_verified")

    # Require the specific reason from the actual application logger.
    expected_message = (
        f"event=campus_sso | result={expected_result} | campus_id=-"
    )
    assert expected_message in caplog.messages
    assert "result=identity_accepted" not in caplog.text

    # Passwords and signed proof must not appear in captured logs.
    assert password not in caplog.text
    assert token not in caplog.text
    assert refused_token not in caplog.text