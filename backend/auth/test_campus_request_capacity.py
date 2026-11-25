# 2026-11-25 - David Noyes
# Verify receiver capacity refusal, logging, and recovery after expiry.

from types import SimpleNamespace

from backend.auth.test_campus_staff_app import BASE, setup
from campus_sso import campus_provider


def test_receiver_capacity_is_logged_and_expired_requests_are_removed(
    setup, monkeypatch, caplog
):
    staff, _, password = setup
    app = staff.application

    # Control only the campus provider module's clock during this test.
    # This avoids waiting five minutes or depending on test execution speed.
    clock = SimpleNamespace(now=1000000.0)

    def current_time():
        return clock.now

    monkeypatch.setattr(
        campus_provider,
        "time",
        SimpleNamespace(time=current_time),
    )

    caplog.set_level("INFO")

    # Each test client represents a separate browser.
    # These requests stay inside Flask; no real server is contacted.
    for _ in range(1000):
        browser = app.test_client()
        response = browser.get(BASE + "/auth/campus/start")
        assert response.status_code == 302

    caplog.clear()

    blocked_browser = app.test_client()
    refused = blocked_browser.get(BASE + "/auth/campus/start")

    assert refused.status_code == 503
    assert (
        "event=campus_sso | result=request_capacity | campus_id=-"
        in caplog.messages
    )
    assert "result=identity_accepted" not in caplog.text
    assert password not in caplog.text
    assert blocked_browser.get(BASE + "/staff").status_code == 403

    with blocked_browser.session_transaction(base_url=BASE) as saved:
        assert "campus_sso_state" not in saved
        assert "pending_mfa_user_id" not in saved
        assert "authenticated_user_id" not in saved
        assert not saved.get("mfa_verified")

    # Advance past request expiry. The next request should clear old entries.
    clock.now += campus_provider.REQUEST_TTL + 1
    caplog.clear()

    accepted = blocked_browser.get(BASE + "/auth/campus/start")

    assert accepted.status_code == 302
    assert accepted.headers["Location"].startswith(
        campus_provider.PROVIDER_URL + "?state="
    )
    assert (
        "event=campus_sso | result=started | campus_id=-"
        in caplog.messages
    )
    assert "result=request_capacity" not in caplog.text
    assert password not in caplog.text

    # Starting campus sign-in does not grant staff access.
    assert blocked_browser.get(BASE + "/staff").status_code == 403