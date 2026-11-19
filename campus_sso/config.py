# 2026-11-19 - David Noyes
"""Importable configuration; importing this module never reads or generates secrets."""
import os
import secrets

SECRET_NAMES = ("FLASK_SECRET_KEY", "CAMPUS_SSO_SIGNING_KEY", "CAMPUS_IDP_COOKIE_SECRET")


def read_secret(name, environ=None):
    """Read a required secret without displaying its value."""
    source = os.environ if environ is None else environ
    value = source.get(name, "")
    if not isinstance(value, str) or len(value) < 32:
        raise RuntimeError(f"{name} is missing or too short. Set it to a random value of at least 32 characters.")
    return value


def load_staff_config(environ=None):
    """Configuration for the ONE staff application and all its blueprints."""
    return {
        "SECRET_KEY": read_secret("FLASK_SECRET_KEY", environ),
        "CAMPUS_SSO_SIGNING_KEY": read_secret("CAMPUS_SSO_SIGNING_KEY", environ),
    }


def load_provider_config(environ=None):
    """The provider has a separate cookie secret, but the same token signing key."""
    return {
        "SECRET_KEY": read_secret("CAMPUS_IDP_COOKIE_SECRET", environ),
        "CAMPUS_SSO_SIGNING_KEY": read_secret("CAMPUS_SSO_SIGNING_KEY", environ),
    }


def make_demo_environment(source):
    """Return an isolated environment for both local child processes."""
    env = dict(source)
    for name in SECRET_NAMES:
        if not env.get(name):
            env[name] = secrets.token_urlsafe(48)
        read_secret(name, env)
    env["PYTHONUNBUFFERED"] = "1"
    return env
