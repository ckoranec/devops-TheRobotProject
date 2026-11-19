# 2026-11-18 - David Noyes - Import the shared factory and attach campus routes.
# No teammate source files are edited by this launcher.
from backend.auth.app import create_app as create_shared_app
from backend.auth.campus_routes import check_database_setup, register_campus_sso
from campus_sso.config import load_staff_config


def create_app():
    config = load_staff_config()
    check_database_setup()
    app = create_shared_app()
    app.config.update(config)
    return register_campus_sso(app)


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5051, debug=False)
