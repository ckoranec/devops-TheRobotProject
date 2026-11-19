# 2026-11-18 - David Noyes - Verify use of Colin's real shared handoff.
from backend.auth import campus_routes, staff_login
from backend.auth.test_campus_staff_app import BASE, setup, begin_campus_mfa


def test_campus_imports_colins_actual_function():
    # Prevent a same-named local copy from silently replacing the shared API.
    assert campus_routes.begin_staff_login is staff_login.begin_staff_login


def test_password_and_campus_use_same_pending_session(setup):
    client, _, password = setup
    with client.session_transaction(base_url=BASE) as saved:
        saved['authenticated_user_id'] = 7
        saved['mfa_verified'] = True
        saved['old_session_marker'] = 'must disappear'
    begin_campus_mfa(setup)
    with client.session_transaction(base_url=BASE) as saved:
        campus_state = dict(saved)
    assert campus_state['pending_mfa_user_id'] == 7
    assert campus_state['mfa_verified'] is False
    assert 'authenticated_user_id' not in campus_state
    assert 'old_session_marker' not in campus_state
    assert client.get(BASE + '/staff').status_code == 403

    password_client = client.application.test_client()
    with password_client.session_transaction(base_url=BASE) as saved:
        saved['authenticated_user_id'] = 7
        saved['mfa_verified'] = True
        saved['old_session_marker'] = 'must disappear'
    response = password_client.post(BASE + '/login', data={
        'username': 'fixture_staff', 'password': password})
    assert response.status_code == 302
    assert response.headers['Location'] == '/verify-code'
    with password_client.session_transaction(base_url=BASE) as saved:
        assert dict(saved) == campus_state
    assert password_client.get(BASE + '/staff').status_code == 403
