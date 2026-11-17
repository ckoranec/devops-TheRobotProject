# LOCAL DEVELOPMENT SETUP:
# Before running this script, execute the following command in PowerShell:
# $env:FLASK_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
#
# Then run: python backend/auth/staff_login.py

# import libaries and tools for html login, authentication, sessions and Pw/user read
import os
import logging
from flask import Flask, render_template_string, request, redirect, url_for, session, Blueprint
from flask.sansio.blueprints import Blueprint

try:
    from .database import get_user_by_username
    from .password_hashing import verify_password
    from .mfa import mfa_bp, init_totp_db
except ImportError:
    from database import get_user_by_username
    from password_hashing import verify_password
    from mfa import mfa_bp, init_totp_db

staff_bp = Blueprint("Staff", __name__)

app = Flask(__name__)

# Flask uses this key to protect session cookies
# Stores it in an environment variable, never in git

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("Set FLASK_SECRET_KEY before starting the application.")

# Connect Shek's MFA routes to our Flask application
app.register_blueprint(mfa_bp, url_prefix="/mfa")
app.register_blueprint(staff_bp)



@staff_bp.route("/")
def home():
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Staff Login</title>
        </head>
        <body>
            <h1>GMU Robot Project - Staff Login</h1>

            <form action="/login" method="POST">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>

                <br><br>

                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>

                <br><br>

                
                 <button type="submit">Log In</button>
            </form>

            <br>

            <p>
                Trouble signing in?
                <a href="/recover">Forgot username or password?</a>
            </p>
        </body>
        </html>

    """)

@staff_bp.route("/login", methods=["POST"])
def login():

    # Clear any previous authentication session before checking credentials
    session.clear()

    # Retrieve the username and the password from the HTML form
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    # Search the database for the entered  username
    user = get_user_by_username(username)

    # Refuse a login if the user does not exist
    if user is None:
        return "Invalid username or password.", 401

    # The database returns the following: (id, username, password_hash)
    stored_hash = user[2]

    # Compares the entered password against the stored bcrypt hash
    if not verify_password(stored_hash, password):
        return "Invalid username or password.", 401

    # Password was verified, but MFA has not been completed yet via Shek's script
    session["pending_mfa_user_id"] = user[0]
    session["mfa_verified"] = False

    # Sends the user to MFA after successful password verification
    return redirect(url_for("mfa.verify_code_page"))


@staff_bp.route("/staff")
def staff_page():

    # Deny access unless the user has completed MFA
    if not session.get("mfa_verified", False):
        return "Access denied. MFA verification required.", 403

    # Confirm that the session belongs to an authenticated user
    if not session.get("authenticated_user_id"):
        return "Access denied. Please log in.", 403

    return "Welcome to the GMU Robot Project staff area!"


@staff_bp.route("/recover")
def recover_account():

    # Display the recovery code entry form
    return render_template_string("""
        <h2>Account Recovery</h2>

        <p>Enter your generated recovery code below.</p>

        <form action="/verify-recovery" method="POST">
            <label for="recovery_code">Recovery Code:</label>
            <input
                type="text"
                id="recovery_code"
                name="recovery_code"
                required
            >

            <br><br>

            <button type="submit">Verify Recovery Code</button>
        </form>

        <br>

        <a href="/">Return to Login</a>
    """)


@staff_bp.route("/logout", methods=["POST"])
def logout():

    # Clear the user's authentication session
    session.clear()

    # Send the user back to the login page
    return redirect(url_for("staff.home"))


if __name__ == "__main__":
    app.run(debug=True)
