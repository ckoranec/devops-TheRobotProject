import io
import base64
import os
import secrets
import sqlite3
import time

import pyotp
import qrcode
from flask import Flask, redirect, render_template_string, request, session, url_for

from seed_users import DB_FILE
from campus_login import find_identity


USER_DB_PATH = DB_FILE          # same DB the login page uses
TOTP_DB_PATH = "totp.db"
PENDING_SECONDS = 240           # time allowed to enter the code
MAX_CODE_TRIES = 5

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

def init_totp_db():
  conn = sqlite3.connect(TOTP_DB_PATH)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS totp_secrets (
            user_id INTEGER PRIMARY KEY,
            totp_secret TEXT NOT NULL
        )
    """)
  conn.commit()
  conn.close()


def verify_2fa(user_id, user_input_code):
    conn_totp = sqlite3.connect(TOTP_DB_PATH)
    cursor_totp = conn_totp.cursor()
    cursor_totp.execute(
        "SELECT totp_secret FROM totp_secrets WHERE user_id = ?", (user_id,)
    )
    result = cursor_totp.fetchone()
    conn_totp.close()

    if not result or not result[0]:
        return False
        
    stored_secret = result[0]
    totp = pyotp.TOTP(stored_secret)
    return totp.verify(user_input_code)

def has_totp_secret(user_id):
    conn_totp = sqlite3.connect(TOTP_DB_PATH)
    cursor_totp = conn_totp.cursor()
    cursor_totp.execute("SELECT totp_secret FROM totp_secrets WHERE user_id = ?", (user_id,))
    result = cursor_totp.fetchone()
    conn_totp.close()
    return result is not None and result[0] != ""

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # Validate username and password credentials
    user = find_identity(username, password)
    
    if user:
        user_id = user['id']
        
        # Store temporary pending state (Official session NOT started yet)
        session['pending_user_id'] = user_id
        
        # Route to setup if they haven't configured 2FA yet, otherwise verification code page
        if has_totp_secret(user_id):
            return redirect(url_for('verify_code_page'))
        else:
            return redirect(url_for('setup_2fa_page'))
            
    return render_template_string(LOGIN_HTML, error="Invalid username or password.")

@app.route('/setup-2fa', methods=['GET', 'POST'])
def setup_2fa_page():
    # Prevent direct URL skipping
    if 'pending_user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['pending_user_id']

    # Fetch username for the provisioning URI
    conn_user = sqlite3.connect(USER_DB_PATH)
    cursor_user = conn_user.cursor()
    cursor_user.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    result = cursor_user.fetchone()
    conn_user.close()
    
    if not result:
        return redirect(url_for('index'))
        
    username = result[0]
    
    # Generate new base32 secret and save it
    secret = pyotp.random_base32()
    conn_totp = sqlite3.connect(TOTP_DB_PATH)
    cursor_totp = conn_totp.cursor()
    cursor_totp.execute(
        "INSERT OR REPLACE INTO totp_secrets (user_id, totp_secret) VALUES (?, ?)",
        (user_id, secret),
    )
    conn_totp.commit()
    conn_totp.close()

    # Create provisioning URI & render QR code as base64 in memory
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=username, issuer_name="Robot Project")

    qr_img = qrcode.make(uri)
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    if request.method == 'POST':
        user_input_code = request.form.get('code')
        if verify_2fa(user_id, user_input_code):
            # Success: Clear temporary pending state and start official session
            session.pop('pending_user_id', None)
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(SETUP_HTML, qr_base64=qr_base64, secret=secret, error="Invalid code. Try again.")

    return render_template_string(SETUP_HTML, qr_base64=qr_base64, secret=secret, error=None)

@app.route('/verify-code', methods=['GET', 'POST'])
def verify_code_page():
    # Prevent direct URL skipping
    if 'pending_user_id' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        user_input_code = request.form.get('code')
        user_id = session['pending_user_id']
        
        if verify_2fa(user_id, user_input_code):
            # Success: Clear temporary pending state and start official session
            session.pop('pending_user_id', None)
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(VERIFY_HTML, error="Invalid verification code.")

    return render_template_string(VERIFY_HTML, error=None)


@app.route('/dashboard')
def dashboard():
    # Protected route checking for official session key
    if 'user_id' not in session:
        return redirect(url_for('index'))
        
    return """
        <h2>Welcome to your Secure Dashboard!</h2>
        <p>You have successfully passed both password authentication and 2FA. change routing in Verify-code page to home page</p>
        <a href="/logout">Logout</a>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
    <h2>Campus Login</h2>
    {% if error %}<p style="color:red;">{{ error }}</p>{% endif %}
    <form method="POST" action="/login">
        <input type="text" name="username" placeholder="Username (try: student)" required><br><br>
        <input type="password" name="password" placeholder="Password (try: password123)" required><br><br>
        <button type="submit">Login</button>
    </form>
</body>
</html>
'''

SETUP_HTML = '''
<!DOCTYPE html>
<html>
<head><title>Setup 2FA</title></head>
<body>
    <h2>Set Up Two-Factor Authentication</h2>
    <p>1. Scan this QR code with Google Authenticator:</p>
    <img src="data:image/png;base64,{{ qr_base64 }}" alt="QR Code">
    <p><strong>Manual Code:</strong> <code>{{ secret }}</code></p>
    <hr>
    <p>2. Enter the 6-digit code from your app to complete setup:</p>
    {% if error %}<p style="color:red;">{{ error }}</p>{% endif %}
    <form method="POST">
        <input type="text" name="code" placeholder="123456" required autocomplete="one-time-code">
        <button type="submit">Verify & Complete</button>
    </form>
</body>
</html>
'''

VERIFY_HTML = '''
<!DOCTYPE html>
<html>
<head><title>Verify Code</title></head>
<body>
    <h2>Two-Factor Authentication</h2>
    {% if error %}<p style="color:red;">{{ error }}</p>{% endif %}
    <form method="POST">
        <p>Enter your 6-digit authenticator code:</p>
        <input type="text" name="code" placeholder="123456" required autocomplete="one-time-code">
        <button type="submit">Verify</button>
    </form>
</body>
</html>
'''

