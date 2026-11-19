# 2026-11-19 - David Noyes - Shared-factory configuration reaches token validation.
import os
import pytest
from flask import Flask
from backend.auth.staff_login import staff_bp
from backend.auth.mfa import mfa_bp
from backend.auth.campus_routes import register_campus_sso
from backend.auth.test_campus_staff_app import BASE, campus_token, setup


@pytest.mark.parametrize('environment', ['missing', 'different'])
def test_receiver_uses_configured_signing_key(setup, monkeypatch, environment):
    _, provider, password = setup
    key = os.environ['CAMPUS_SSO_SIGNING_KEY']
    app = Flask(__name__)
    app.secret_key = os.environ["FLASK_SECRET_KEY"]
    app.register_blueprint(staff_bp)
    app.register_blueprint(mfa_bp)
    original_session_key = app.secret_key
    app.config['CAMPUS_SSO_SIGNING_KEY'] = key
    if environment == 'missing':
        monkeypatch.delenv('CAMPUS_SSO_SIGNING_KEY')
    else:
        monkeypatch.setenv('CAMPUS_SSO_SIGNING_KEY', 'different-environment-key-' * 3)
    register_campus_sso(app)
    client = app.test_client()
    token = campus_token((client, provider, password))
    response = client.post(BASE + '/auth/campus/callback', data={'token': token})
    assert response.status_code == 302
    assert '/verify-code' in response.headers['Location']
    assert app.secret_key == original_session_key
    with client.session_transaction(base_url=BASE) as saved:
        assert saved['pending_mfa_user_id'] == 7
        assert not saved.get('mfa_verified')
    assert client.get(BASE + '/staff').status_code == 403


@pytest.mark.parametrize('key', ['', 'short', None])
def test_invalid_explicit_config_does_not_fall_back(setup, key):
    app = Flask(__name__)
    app.config['CAMPUS_SSO_SIGNING_KEY'] = key
    with pytest.raises(RuntimeError, match='CAMPUS_SSO_SIGNING_KEY'):
        register_campus_sso(app)
    assert not app.blueprints


def test_environment_fallback_and_repeat_registration(setup):
    app = Flask(__name__)
    app.secret_key = os.environ["FLASK_SECRET_KEY"]
    app.register_blueprint(staff_bp)
    app.register_blueprint(mfa_bp)
    key = os.environ['CAMPUS_SSO_SIGNING_KEY']
    register_campus_sso(app)
    routes = list(app.url_map.iter_rules())
    register_campus_sso(app)
    assert list(app.url_map.iter_rules()) == routes
    assert app.config['CAMPUS_SSO_SIGNING_KEY'] == key
