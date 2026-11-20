# LOCAL DEVELOPMENT SETUP:
# Before running this script, execute the following command in PowerShell:
# $env:FLASK_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
#
# Then run: python -m backend.auth.app

# import libaries and tools for html login, authentication, sessions and Pw/user read
import os
from mfa import get_lockout_remaining

import logging
import time

from flask import Flask, render_template_string, request, redirect, url_for, session, Blueprint


try:
    from .database import get_user_by_username
    from .password_hashing import verify_password
    from .mfa import mfa_bp, init_totp_db
except ImportError:
    from database import get_user_by_username
    from password_hashing import verify_password
    from mfa import mfa_bp, init_totp_db

staff_bp = Blueprint("staff", __name__)
IDLE_TIMEOUT_SECONDS = 15 * 60

@staff_bp.before_request
def check_staff_idle_timeout():

    # Only check fully authenticated staff sessions
    if not session.get("mfa_verified") or not session.get("authenticated_user_id"):
        return

    current_time = time.time()
    last_activity = session.get("last_activity")

    # Initialize activity tracking using the existing login timestamp
    if last_activity is None:
        last_activity = session.get("pending_started")

        if last_activity is None:
            session.clear()
            return redirect(url_for("staff.home"))

    # Log out after 15 minutes without activity
    if current_time - last_activity >= IDLE_TIMEOUT_SECONDS:
        session.clear()
        return redirect(url_for("staff.home"))

    # Record the latest authenticated activity
    session["last_activity"] = current_time

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

    # Retrieve the username and password from the HTML form
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    # Search the database for the entered username
    user = get_user_by_username(username)

    # Refuse login if the username does not exist
    if user is None:
        logging.warning("Staff login failed: unknown username")
        return "Invalid username or password.", 401

    # The database returns: (id, username, password_hash)
    stored_hash = user[2]

    # Refuse login if the password is incorrect
    if not verify_password(stored_hash, password):
        logging.warning("Staff login failed: invalid password for user ID %s", user[0])
        return "Invalid username or password.", 401

    remaining = get_lockout_remaining(user[0])
    if remaining > 0:
        logging.warning(f"Blocked login during cooldown | user_id={user[0]} ({username}) | remaining={remaining}s")
        return f"Too many attempts or recent sign-in timeout. Try again in {remaining} seconds.", 429

    # Record successful password verification
    logging.info("Staff password verified for user ID %s; MFA pending", user[0])

    # Credentials are verified; initiate the shared MFA process
    return begin_staff_login(user[0])

def begin_staff_login(staff_id):
    # Clears any previous authentication session
    session.clear()

    # Identifies the staff user who needs to complete MFA
    session["pending_mfa_user_id"] = staff_id
    session["mfa_verified"] = False
    session["pending_started"] = time.time()
    # Sends the staff user to Shek's MFA verification page
    return redirect(url_for("mfa.verify_code_page"))

@staff_bp.route("/staff")
def staff_page():

    # Deny access unless the user has completed MFA
    if not session.get("mfa_verified", False):
        return "Access denied. MFA verification required.", 403

    # Confirm that the session belongs to an authenticated user
    if not session.get("authenticated_user_id"):
        return "Access denied. Please log in.", 403

    # Displays the protected staff page with an added logout button
    return render_template_string("""
           <!DOCTYPE html>
           <html>
           <head>
               <title>GMU Staff Area</title>
           </head>
           <body>
               <h1>Welcome to the GMU Robot Project staff area!</h1>

               <form action="{{ url_for('staff.logout') }}" method="POST">
                   <button type="submit">Log Out</button>
               </form>
           </body>
           </html>
       """)


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

            <!-- Placeholder for Satchi's recovery functionality -->
            <button type="button" disabled>Send Recovery Code</button>

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



