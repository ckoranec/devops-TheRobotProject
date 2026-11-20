import logging
import os
import secrets
import time

from flask import Flask
from .keys import resolve_secret
from .database import DB_FILE, create_staff_campus_mapping
from .staff_login import staff_bp
from .mfa import mfa_bp, init_totp_db
from .campus_routes import register_campus_sso
from .campus_directory import create_campus_table


def create_app():
    app = Flask(__name__)

    app.secret_key = resolve_secret("FLASK_SECRET_KEY", allow_ephemeral=True)
    app.config["CAMPUS_SSO_SIGNING_KEY"] = resolve_secret(
        "CAMPUS_SSO_SIGNING_KEY", allow_ephemeral=False
    )
    app.config["CAMPUS_IDP_COOKIE_SECRET"] = resolve_secret(
        "CAMPUS_IDP_COOKIE_SECRET", allow_ephemeral=True
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