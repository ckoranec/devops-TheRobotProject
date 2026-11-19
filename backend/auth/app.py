import logging
import os
import secrets

from flask import Flask
from .database import DB_FILE, create_staff_campus_mapping
from .staff_login import staff_bp
from .mfa import mfa_bp, init_totp_db
from .campus_routes import register_campus_sso
from .campus_directory import create_campus_table

def ensure_secret(name):
    """Use the env value if valid; otherwise generate one (dev) or fail (production)."""
    value = os.environ.get(name, "")
    if len(value) >= 32:
        return value
    if os.environ.get("APP_ENV") == "production":
        raise RuntimeError(f"Set {name} to a random value of at least 32 characters.")
    value = secrets.token_hex(32)
    os.environ[name] = value      # so read_secret() and the reloader child see it
    print(f"WARNING: {name} not set. Generated temporary dev key.")
    return value

def create_app():
    app = Flask(__name__)

    app.secret_key = ensure_secret("FLASK_SECRET_KEY")
    ensure_secret("CAMPUS_SSO_SIGNING_KEY")
    ensure_secret("CAMPUS_IDP_COOKIE_SECRET")

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("APP_ENV") == "production",
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "account_activity.log"),
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )

    init_totp_db()
    create_staff_campus_mapping()
    create_campus_table(DB_FILE)

    app.register_blueprint(staff_bp)    # /, /login, /staff, /logout, /recover
    app.register_blueprint(mfa_bp)      # /setup-2fa, /verify-code, /reset-2fa
    register_campus_sso(app)            # /campus, /campus/continue, /campus/logout,
                                        # /auth/campus/start, /auth/campus/callback
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5051, debug=True)