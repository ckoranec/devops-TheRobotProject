# import libaries and tools for html login, authentication, sessions and Pw/user read
import os
from flask import Flask, render_template_string, request, redirect, url_for, session

try:
    from .database import get_user_by_username
    from .password_hashing import verify_password
except ImportError:
    from database import get_user_by_username
    from password_hashing import verify_password


app = Flask(__name__)

# Flask uses this key to sign session cookies
# Store it in an environment variable - NOT in Git
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("Set FLASK_SECRET_KEY before starting the application.")



@app.route("/")
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
        </body>
        </html>
    """)


@app.route("/login", methods=["POST"])
def login():

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

    # If both checks passed then authentication succeeds
    return "Password verified successfully!"

if __name__ == "__main__":
    app.run(debug=True)
