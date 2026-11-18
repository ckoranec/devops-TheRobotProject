import logging
import os
import secrets

from flask import Flask

from .staff_login import staff_bp
from .mfa import mfa_bp, init_totp_db



def create_app():
    app = Flask(__name__)

    key = os.environ.get("FLASK_SECRET_KEY")
    if not key:
        if os.environ.get("APP_ENV") == "production":
            raise RuntimeError("Set FLASK_SECRET_KEY before starting the application in production.")
        key = secrets.token_hex(32)
        print("WARNING: FLASK_SECRET_KEY not set. Generated temporary dev key.")
    app.secret_key = key

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

    app.register_blueprint(staff_bp)    # /, /login, /staff, /logout, /recover
    app.register_blueprint(mfa_bp)      # /setup-2fa, /verify-code, /reset-2fa
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5051, debug=True)