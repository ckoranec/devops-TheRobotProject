# 2026-11-20 - David Noyes
"""Secret configuration shared by the campus provider and demo launcher."""

import os
import secrets

SECRET_NAMES = (
    "FLASK_SECRET_KEY",
    "CAMPUS_SSO_SIGNING_KEY",
    "CAMPUS_IDP_COOKIE_SECRET",
)

STARTUP_GUIDANCE = (
    "For the full local demo, run python -m campus_sso.run_demo. "
    "For separate terminals, configure the same "
    "CAMPUS_SSO_SIGNING_KEY in both processes. "
    "Configure FLASK_SECRET_KEY for the staff application and "
    "CAMPUS_IDP_COOKIE_SECRET for the provider separately. "
    "Do not share or print secret values."
)


def read_secret(name, environ=None):
    """Read a required secret without displaying its value."""
    source = os.environ if environ is None else environ
    value = source.get(name, "")
    if not isinstance(value, str) or len(value) < 32:
        raise RuntimeError(
            f"{name} is missing or too short. "
            "Set it to a random value of at least 32 characters. "
            + STARTUP_GUIDANCE
        )
    return value


def load_staff_config(environ=None):
    """Load configuration for the shared staff application."""
    return {
        "SECRET_KEY": read_secret("FLASK_SECRET_KEY", environ),
        "CAMPUS_SSO_SIGNING_KEY": read_secret(
            "CAMPUS_SSO_SIGNING_KEY", environ
        ),
    }


def load_provider_config(environ=None):
    """Use a separate provider cookie key and the shared token key."""
    return {
        "SECRET_KEY": read_secret("CAMPUS_IDP_COOKIE_SECRET", environ),
        "CAMPUS_SSO_SIGNING_KEY": read_secret(
            "CAMPUS_SSO_SIGNING_KEY", environ
        ),
    }


def make_demo_environment(source):
    """Generate missing demo keys once for both child processes."""
    env = dict(source)
    for name in SECRET_NAMES:
        if not env.get(name):
            env[name] = secrets.token_urlsafe(48)
        read_secret(name, env)
    env["PYTHONUNBUFFERED"] = "1"
    return env