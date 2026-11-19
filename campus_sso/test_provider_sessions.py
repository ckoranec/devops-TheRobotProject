# 2026-11-19 - David Noyes - Remembered provider authentication and its boundaries.
import re
import secrets
import sqlite3
from html import unescape

import pytest
import pyotp
from backend.auth import database, mfa
from backend.auth.test_campus_staff_app import BASE, PROVIDER, setup
from campus_sso.campus_provider import create_provider, token_serializer, check_token
from campus_sso.provider_sessions import COOKIE_NAME, IDLE_SECONDS, MAX_SECONDS, ProviderSessions
import os


def token_from(response):
    return unescape(re.search(r'name="token" value="([^"]+)"', response.text).group(1))


def password_login(setup, username='campus_staff', password=None):
    staff, provider, saved = setup
    start = staff.get(BASE + '/auth/campus/start')
    page = provider.get(start.headers['Location'])
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    response = provider.post(PROVIDER + '/login', data={
        'username': username, 'password': saved if password is None else password, 'csrf': csrf})
    return response


def new_request(setup):
    start = setup[0].get(BASE + '/auth/campus/start')
    return setup[1].get(start.headers['Location'])


def test_remembered_provider_issues_new_request_bound_proof(setup, caplog):
    caplog.set_level('INFO')
    first = password_login(setup)
    second = new_request(setup)
    assert 'name="password"' not in second.text
    signer = token_serializer(os.environ['CAMPUS_SSO_SIGNING_KEY'])
    a, b = (signer.loads(token_from(r)) for r in (first, second))
    assert a['sub'] == b['sub'] == 'CAMPUS-1001'
    assert a['state'] != b['state'] and a['jti'] != b['jti']
    assert b['exp'] - b['iat'] == 60
    check_token(signer, token_from(second), b['state'])
    assert 'result=session_reused' in caplog.text
    assert setup[2] not in caplog.text and token_from(second) not in caplog.text
    cookie = setup[1].get_cookie(COOKIE_NAME, domain='127.0.0.1')
    assert cookie.http_only and cookie.same_site == 'Lax'
    assert 'CAMPUS' not in cookie.value and setup[2] not in cookie.value


def test_staff_logout_preserves_provider_but_next_login_requires_mfa(setup):
    staff = setup[0]
    proof = password_login(setup)
    staff.post(BASE + '/auth/campus/callback', data={'token': token_from(proof)})
    staff.get(BASE + '/verify-code', follow_redirects=True)
    code = pyotp.TOTP(mfa.get_totp_record(7)[0]).now()
    result = staff.post(BASE + '/setup-2fa', data={'code': code}, follow_redirects=True)
    assert 'Welcome to the GMU Robot Project staff area!' in result.text
    staff.post(BASE + '/logout')
    assert setup[1].get_cookie(COOKIE_NAME, domain='127.0.0.1') is not None
    response = new_request(setup)
    callback = staff.post(BASE + '/auth/campus/callback', data={'token': token_from(response)})
    assert callback.headers['Location'] == '/verify-code'
    assert staff.get(BASE + '/staff').status_code == 403
    with staff.session_transaction(base_url=BASE) as saved:
        assert saved['mfa_verified'] is False
        assert saved['pending_mfa_user_id'] == 7
        assert 'authenticated_user_id' not in saved


def test_remembered_student_still_has_no_staff_mapping(setup, caplog):
    caplog.set_level('INFO')
    first = password_login(setup, 'campus_student')
    for response in (first,):
        assert setup[0].post(BASE + '/auth/campus/callback', data={'token': token_from(response)}).status_code == 403
    second = new_request(setup)
    assert 'name="password"' not in second.text
    assert setup[0].post(BASE + '/auth/campus/callback', data={'token': token_from(second)}).status_code == 403
    assert 'result=no_staff_role | campus_id=CAMPUS-2001' in caplog.text


@pytest.mark.parametrize('reason', ['idle', 'absolute', 'tampered', 'restart', 'revoked', 'password_changed', 'account_deleted'])
def test_remembered_session_ends(setup, reason, caplog):
    caplog.set_level('INFO')
    password_login(setup)
    provider = setup[1]
    store = provider.application.extensions['campus_provider_sessions']
    cookie = provider.get_cookie(COOKIE_NAME, domain='127.0.0.1')
    record = store.records[cookie.value]
    now = store.clock()
    if reason == 'idle':
        record['seen'] = now - IDLE_SECONDS
    elif reason == 'absolute':
        record['created'] = now - MAX_SECONDS
        record['seen'] = now
    elif reason == 'tampered':
        provider.set_cookie(COOKIE_NAME, secrets.token_urlsafe(32), domain='127.0.0.1')
    elif reason == 'restart':
        provider = create_provider(database.DB_FILE).test_client()
        provider.set_cookie(COOKIE_NAME, cookie.value, domain='127.0.0.1')
    elif reason == 'revoked':
        store.revoke(cookie.value)
    else:
        with sqlite3.connect(database.DB_FILE) as conn:
            if reason == 'password_changed':
                conn.execute("UPDATE campus_accounts SET password_hash = 'changed-test-hash' WHERE campus_id = 'CAMPUS-1001'")
            else:
                conn.execute("DELETE FROM campus_accounts WHERE campus_id = 'CAMPUS-1001'")
    start = setup[0].get(BASE + '/auth/campus/start')
    page = provider.get(start.headers['Location'])
    assert 'name="password"' in page.text and 'name="token"' not in page.text
    assert provider.get_cookie(COOKIE_NAME, domain='127.0.0.1') is None


def test_provider_logout_is_csrf_protected_and_revokes_saved_cookie(setup):
    password_login(setup)
    provider = setup[1]
    cookie = provider.get_cookie(COOKIE_NAME, domain='127.0.0.1').value
    assert provider.post(PROVIDER + '/logout', data={'csrf': 'bad'}).status_code == 403
    assert cookie in provider.application.extensions['campus_provider_sessions'].records
    page = provider.get(PROVIDER + '/logout')
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    assert provider.post(PROVIDER + '/logout', data={'csrf': csrf}).status_code == 200
    assert cookie not in provider.application.extensions['campus_provider_sessions'].records
    provider.set_cookie(COOKIE_NAME, cookie, domain='127.0.0.1')
    assert 'name="password"' in new_request(setup).text


def test_invalid_password_and_invalid_state_are_logged(setup, caplog):
    caplog.set_level('INFO')
    assert password_login(setup, password='wrong').status_code == 401
    assert 'result=invalid_credentials' in caplog.text
    assert setup[1].get(PROVIDER + '/login?state=bad').status_code == 400
    assert 'result=invalid_request' in caplog.text
    assert setup[2] not in caplog.text


def test_store_rotates_ids_and_bounds_capacity():
    now = [0.0]
    store = ProviderSessions(clock=lambda: now[0], capacity=1)
    identity = {'campus_id': 'CAMPUS-1001'}
    old = store.create(identity, 'fingerprint')
    new = store.create(identity, 'fingerprint', previous=old)
    assert new != old and old not in store.records
    with pytest.raises(RuntimeError):
        store.create(identity, 'fingerprint')
    now[0] = IDLE_SECONDS
    store.create(identity, 'fingerprint')
    assert len(store.records) == 1


def test_reuse_refreshes_idle_but_does_not_extend_absolute_lifetime(monkeypatch):
    from campus_sso import provider_sessions
    now = [0.0]
    identity = {'campus_id': 'CAMPUS-1001', 'affiliation': 'staff'}
    monkeypatch.setattr(provider_sessions, 'current_identity', lambda *args: (identity, 'fingerprint'))
    store = ProviderSessions(clock=lambda: now[0])
    key = store.create(identity, 'fingerprint')
    for stamp in (800, 1600, 2400, 3200):
        now[0] = stamp
        assert store.lookup(key)[0] == identity
    now[0] = MAX_SECONDS
    assert store.lookup(key) == (None, 'session_expired')


def test_returned_proof_cannot_be_replayed_after_remembered_signin(setup):
    password_login(setup)
    response = new_request(setup)
    token = token_from(response)
    staff = setup[0]
    assert staff.post(BASE + '/auth/campus/callback', data={'token': token}).status_code == 302
    assert staff.post(BASE + '/auth/campus/callback', data={'token': token}).status_code == 403
    assert staff.get(BASE + '/staff').status_code == 403
