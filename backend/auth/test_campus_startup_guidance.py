# 2026-11-20 - David Noyes
# Verify startup guidance and rejection of mismatched signing keys.

import os

import pytest
from flask import Flask

from backend.auth.campus_routes import register_campus_sso
from backend.auth.mfa import mfa_bp
from backend.auth.staff_login import staff_bp
from backend.auth.test_campus_staff_app import BASE, campus_token, setup
from campus_sso import config


@pytest.mark.parametrize("name", config.SECRET_NAMES)
@pytest.mark.parametrize("value", [None, "", "private-short-value"])
def test_invalid_secret_explains_startup_without_disclosing_value(name, value):
    environment = {} if value is None else {name: value}
    with pytest.raises(RuntimeError) as error:
        config.read_secret(name, environment)

    message = str(error.value)
    assert name in message
    assert "python -m campus_sso.run_demo" in message
    assert "same CAMPUS_SSO_SIGNING_KEY in both processes" in message
    if value:
        assert value not in message


def test_demo_environment_supplies_matching_keys_without_changing_parent():
    parent = {}
    environment = config.make_demo_environment(parent)
    staff = config.load_staff_config(environment)
    provider = config.load_provider_config(environment)

    assert parent == {}
    assert staff["CAMPUS_SSO_SIGNING_KEY"] == provider["CAMPUS_SSO_SIGNING_KEY"]
    assert staff["SECRET_KEY"] != provider["SECRET_KEY"]
    assert all(len(environment[name]) >= 32 for name in config.SECRET_NAMES)


def test_mismatched_provider_and_receiver_keys_refuse_access(setup, caplog):
    _, provider, password = setup
    provider_key = os.environ["CAMPUS_SSO_SIGNING_KEY"]

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = os.environ["FLASK_SECRET_KEY"]
    app.config["CAMPUS_SSO_SIGNING_KEY"] = provider_key + "-different"
    app.register_blueprint(staff_bp)
    app.register_blueprint(mfa_bp)
    register_campus_sso(app)

    client = app.test_client()
    token = campus_token((client, provider, password))

    caplog.clear()
    with caplog.at_level("INFO", logger=app.logger.name):
        response = client.post(
            BASE + "/auth/campus/callback",
            data={"token": token},
        )

    assert response.status_code == 403
    assert "Staff access refused" in response.text
    assert client.get(BASE + "/staff").status_code == 403
    assert any(
        "event=campus_sso | result=invalid_signature | campus_id=-"
        in message
        for message in caplog.messages
    )

    with client.session_transaction(base_url=BASE) as saved:
        assert "pending_mfa_user_id" not in saved
        assert "authenticated_user_id" not in saved
        assert not saved.get("mfa_verified")

    for value in (
        password,
        token,
        provider_key,
        app.config["CAMPUS_SSO_SIGNING_KEY"],
    ):
        assert value not in caplog.text
