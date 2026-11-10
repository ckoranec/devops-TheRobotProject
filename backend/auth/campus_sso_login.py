# 2026-11-10 — David Noyes — Campus SSO provider launcher.
# Import the separate provider without duplicating its implementation.
# Preserve backend/auth/campus_login.py because teammates depend on it.
# Run from the project root: python -m backend.auth.campus_sso_login

from campus_sso.campus_login import create_provider  # Reuse the existing provider.


if __name__ == "__main__":  # Start only when explicitly executed.
    app = create_provider()  # Configure the provider using environment secrets.
    app.run(  # Launch the local demonstration server.
        host="127.0.0.1",  # Accept connections from this computer only.
        port=5052,  # Use the campus provider's designated port.
        debug=False,  # Disable the interactive debugger.
    )  # Finish configuring the server.
