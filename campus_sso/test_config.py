# 2026-11-19 - David Noyes - Importable secret configuration contract.
import importlib
import pytest
from campus_sso import config


def test_staff_and_provider_share_only_signing_key():
    env = dict(zip(config.SECRET_NAMES, ('s' * 48, 't' * 48, 'p' * 48)))
    staff = config.load_staff_config(env)
    provider = config.load_provider_config(env)
    assert staff['SECRET_KEY'] == env['FLASK_SECRET_KEY']
    assert provider['SECRET_KEY'] == env['CAMPUS_IDP_COOKIE_SECRET']
    assert staff['SECRET_KEY'] != provider['SECRET_KEY']
    assert staff['CAMPUS_SSO_SIGNING_KEY'] == provider['CAMPUS_SSO_SIGNING_KEY']
    assert len(env) == 3


@pytest.mark.parametrize('name', config.SECRET_NAMES)
@pytest.mark.parametrize('value', ['', 'private-short-value'])
def test_invalid_secret_fails_without_disclosure(name, value):
    with pytest.raises(RuntimeError) as error:
        config.read_secret(name, {name: value})
    assert name in str(error.value)
    if value:
        assert value not in str(error.value)


def test_import_does_not_require_secrets(monkeypatch):
    for name in config.SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    importlib.reload(config)
    assert callable(config.load_staff_config)


def test_legacy_provider_import_uses_shared_reader():
    from campus_sso.campus_provider import read_secret
    assert read_secret.__module__ == 'campus_sso.config'


def test_loaders_need_only_their_own_secrets():
    assert config.load_staff_config({'FLASK_SECRET_KEY': 's'*48, 'CAMPUS_SSO_SIGNING_KEY': 't'*48})
    assert config.load_provider_config({'CAMPUS_IDP_COOKIE_SECRET': 'p'*48, 'CAMPUS_SSO_SIGNING_KEY': 't'*48})
