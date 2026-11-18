# 2026-11-18 - David Noyes
# Launcher configuration and failure-handling tests.
# The occupied-port test uses a temporary port, not the live provider port.

import socket

import pytest

from campus_sso.run_demo import (
    make_environment,
    require_free_ports,
    wait_ready,
)


def test_launcher_generates_secrets_without_mutating_parent():
    source = {"EXISTING": "preserved"}
    env = make_environment(source)

    assert source == {"EXISTING": "preserved"}

    for name in (
        "FLASK_SECRET_KEY",
        "CAMPUS_SSO_SIGNING_KEY",
        "CAMPUS_IDP_COOKIE_SECRET",
    ):
        assert len(env[name]) >= 32

    assert env["EXISTING"] == "preserved"


def test_launcher_rejects_short_configured_secret():
    with pytest.raises(RuntimeError, match="too short"):
        make_environment({"CAMPUS_SSO_SIGNING_KEY": "short"})


def test_launcher_preserves_existing_signing_key():
    original_key = "x" * 48
    env = make_environment({"CAMPUS_SSO_SIGNING_KEY": original_key})

    assert env["CAMPUS_SSO_SIGNING_KEY"] == original_key


def test_launcher_refuses_occupied_port():
    with socket.socket() as sock:
        # Port zero asks Windows to allocate an available temporary port.
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.listen()

        # Keep that port occupied while checking the launcher's refusal.
        with pytest.raises(RuntimeError, match=str(port)):
            require_free_ports((port,))


def test_launcher_reports_early_child_failure():
    class FailedChild:
        def poll(self):
            return 1

    with pytest.raises(RuntimeError, match="stopped during startup"):
        wait_ready([FailedChild()])