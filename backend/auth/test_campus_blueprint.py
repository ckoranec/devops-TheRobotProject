# 2026-11-18 - David Noyes - Blueprint, returning-session, and logout checks.
import re
import pyotp
from backend.auth import mfa
from backend.auth.test_campus_staff_app import BASE, setup, begin_campus_mfa


def complete_mfa(setup):
    client = begin_campus_mfa(setup)
    client.get(BASE + "/verify-code", follow_redirects=True)
    code = pyotp.TOTP(mfa.get_totp_record(7)[0]).now()
    response = client.post(BASE + "/setup-2fa", data={"code": code}, follow_redirects=True)
    assert "Welcome to the GMU Robot Project staff area!" in response.text
    return client


def test_campus_routes_belong_to_blueprint(setup):
    app = setup[0].application
    assert "campus" in app.blueprints
    for path in ("/campus", "/auth/campus/start", "/auth/campus/callback", "/campus/logout"):
        rules = [r for r in app.url_map.iter_rules() if r.rule == path]
        assert len(rules) == 1
        assert rules[0].endpoint.startswith("campus.")


def test_returning_verified_session_continues_without_new_mfa(setup):
    client = complete_mfa(setup)
    with client.session_transaction(base_url=BASE) as saved:
        user_id = saved["authenticated_user_id"]
    assert "Continue to staff area" in client.get(BASE + "/campus").text
    result = client.get(BASE + "/campus/continue", follow_redirects=True)
    assert "Welcome to the GMU Robot Project staff area!" in result.text
    with client.session_transaction(base_url=BASE) as saved:
        assert saved["authenticated_user_id"] == user_id
        assert saved["mfa_verified"] is True
        assert "pending_mfa_user_id" not in saved


def test_pending_mfa_cannot_continue(setup):
    client = begin_campus_mfa(setup)
    assert "Continue to staff area" not in client.get(BASE + "/campus").text
    assert client.get(BASE + "/campus/continue").headers["Location"] == "/campus"
    assert client.get(BASE + "/staff").status_code == 403


def test_anonymous_cannot_continue(setup):
    client = setup[0]
    assert client.get(BASE + "/campus/continue").headers["Location"] == "/campus"
    assert client.get(BASE + "/staff").status_code == 403


def test_campus_logout_clears_verified_session_and_returns_to_campus(setup):
    client = complete_mfa(setup)
    page = client.get(BASE + "/campus")
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    response = client.post(BASE + "/campus/logout", data={"csrf": csrf})
    assert response.headers["Location"] == "/campus"
    assert client.get(BASE + "/staff").status_code == 403
    with client.session_transaction(base_url=BASE) as saved:
        assert not saved


def test_campus_logout_requires_valid_form(setup):
    client = complete_mfa(setup)
    assert client.post(BASE + "/campus/logout").status_code == 403
    assert client.get(BASE + "/staff").status_code == 200


def test_explicit_new_login_requires_mfa_again(setup):
    client = complete_mfa(setup)
    begin_campus_mfa(setup)
    assert client.get(BASE + "/staff").status_code == 403
    with client.session_transaction(base_url=BASE) as saved:
        assert saved["mfa_verified"] is False
        assert "authenticated_user_id" not in saved
