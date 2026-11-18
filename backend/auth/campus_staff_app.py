# 2026-11-18 - David Noyes - Import the shared factory and attach campus routes.
# No teammate source files are edited by this launcher.
from backend.auth.app import create_app as create_shared_app
from backend.auth.campus_routes import check_database_setup, register_campus_sso
from campus_sso.campus_provider import read_secret


def create_app():
    read_secret("FLASK_SECRET_KEY")
    read_secret("CAMPUS_SSO_SIGNING_KEY")
    check_database_setup()
    return register_campus_sso(create_shared_app())


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5051, debug=False)
