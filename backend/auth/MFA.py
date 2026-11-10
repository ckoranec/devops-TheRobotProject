import io
import base64
import os
import secrets
import sqlite3
import time

import pyotp
import qrcode
from flask import Flask, redirect, render_template_string, request, session, url_for, abort

from seed_users import DB_FILE
from campus_login import find_identity


USER_DB_PATH = DB_FILE          # same DB the login page uses
TOTP_DB_PATH = "totp.db"
PENDING_SECONDS = 240           # time allowed to enter the code
MAX_CODE_TRIES = 2

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

def clear_totp_db():
    """Drops and re-initializes the TOTP table to clear all stored secrets."""
    conn = sqlite3.connect(TOTP_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS totp_secrets")
    conn.commit()
    conn.close()
    init_totp_db()
    print("TOTP database cleared and re-initialized.")

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
    if 'pending_user_id' not in session:
        return abort(404)

    user_id = session['pending_user_id']

    conn_user = sqlite3.connect(USER_DB_PATH)
    cursor_user = conn_user.cursor()
    cursor_user.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    result = cursor_user.fetchone()
    conn_user.close()
    
    if not result:
        return abort(404)
        
    username = result[0]
    
    # Check if a secret was ALREADY generated for this user in totp.db
    conn_totp = sqlite3.connect(TOTP_DB_PATH)
    cursor_totp = conn_totp.cursor()
    cursor_totp.execute("SELECT totp_secret FROM totp_secrets WHERE user_id = ?", (user_id,))
    row = cursor_totp.fetchone()
    
    if row and row[0]:
        secret = row[0] # Reuse the existing secret!
    else:
        # Generate new base32 secret only if it doesn't exist yet
        secret = pyotp.random_base32()
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
        return abort(404)

    # Initialize tracking fields in session if they don't exist
    if 'totp_attempts' not in session:
        session['totp_attempts'] = 0
    if 'totp_lockout_until' not in session:
        session['totp_lockout_until'] = 0

    current_time = time.time()

    #  Check if the user is currently locked out
    if current_time < session['totp_lockout_until']:
        remaining_seconds = int(session['totp_lockout_until'] - current_time)
        error_msg = f"Too many failed attempts. Please try again in {remaining_seconds} seconds."
        return render_template_string(VERIFY_HTML, error=error_msg, locked=True)

    # If lockout timer has expired, reset counters
    if session['totp_lockout_until'] > 0 and current_time >= session['totp_lockout_until']:
        session['totp_attempts'] = 0
        session['totp_lockout_until'] = 0

    if request.method == 'POST':
        user_input_code = request.form.get('code')
        user_id = session['pending_user_id']
        
        if verify_2fa(user_id, user_input_code):
            # Success: Clear all temporary states and start official session
            session.pop('pending_user_id', None)
            session.pop('totp_attempts', None)
            session.pop('totp_lockout_until', None)
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
        else:
            session['totp_attempts'] += 1
            
            # 3. Check if max attempts reached
            if session['totp_attempts'] >= MAX_CODE_TRIES:
                session['totp_lockout_until'] = time.time() + 30  # Lock out for 30 seconds
                return render_template_string(VERIFY_HTML, error="Too many failed attempts. Locked out for 1 minute.", locked=True)
            
            remaining_tries = MAX_CODE_TRIES - session['totp_attempts']
            return render_template_string(VERIFY_HTML, error=f"Invalid verification code. {remaining_tries} attempts remaining.", locked=False)

    return render_template_string(VERIFY_HTML, error=None, locked=False)


@app.route('/dashboard')
def dashboard():
    # Protected route checking for official session key
    if 'user_id' not in session:
        return abort(404)
        
    return """
        <h2>Welcome to your Secure Dashboard!</h2>
        <p>You have successfully passed both password authentication and 2FA. Change routing in Verify-code page to next needed page</p>
        <a href="/logout">Logout</a>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template_string(LOGIN_HTML, error=None)


@app.route('/reset-2fa')
def reset_2fa():
    clear_totp_db()
    session.clear()
    return "TOTP database has been cleared! <a href='/'>Go back to login</a>"

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
    <h2>Campus Login</h2>
    {% if error %}<p style="color:red;">{{ error }}</p>{% endif %}
    <form method="POST" action="/login">
        <input type="text" name="username" placeholder="Username" required><br><br>
        <input type="password" name="password" placeholder="Password" required><br><br>
        <button type="submit">Login</button>
    </form>
</body>
</html>
'''
 
SETUP_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Setup 2FA — MaxBytes Campus</title>
    <style>
        body {
            margin: 0;
            padding: 24px;
            font-family: Arial, sans-serif;
            background: #f3f5f7;
            color: #17212b;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        main {
            width: 100%;
            max-width: 480px;
            padding: 32px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            box-sizing: border-box;
            text-align: center;
        }
        h2 {
            margin-top: 0;
            color: #075c45;
        }
        p {
            color: #555;
            font-size: 14px;
            line-height: 1.5;
            text-align: left;
        }
        .qr-container {
            margin: 16px 0;
            padding: 12px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            display: inline-block;
        }
        img {
            max-width: 180px;
            height: auto;
            display: block;
            margin: 0 auto;
        }
        code {
            background: #eef2f6;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 13px;
            color: #333;
            word-break: break-all;
        }
        input[type="text"] {
            box-sizing: border-box;
            width: 100%;
            margin-top: 8px;
            padding: 12px;
            border: 1px solid #aab5bf;
            border-radius: 6px;
            font-size: 18px;
            text-align: center;
            letter-spacing: 4px;
        }
        button {
            width: 100%;
            margin-top: 20px;
            padding: 12px 18px;
            border: 0;
            border-radius: 6px;
            background: #075c45;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover {
            background: #054835;
        }
        .error {
            color: #a01818;
            background: #fdf2f2;
            padding: 10px;
            border-radius: 6px;
            font-weight: bold;
            margin-bottom: 16px;
            text-align: center;
        }
        hr {
            border: 0;
            border-top: 1px solid #d5dce2;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <main>
        <h2>Set Up Two-Factor Authentication</h2>
        <p><strong>Step 1:</strong> Scan this QR code with Google Authenticator or your authenticator app:</p>
        
        <div class="qr-container">
            <img src="data:image/png;base64,{{ qr_base64 }}" alt="2FA QR Code">
        </div>
        
        <p style="text-align: center; font-size: 13px; margin-top: 4px;">
            Can't scan? Use manual code: <br><br><code>{{ secret }}</code>
        </p>
        
        <hr>
        
        <p><strong>Step 2:</strong> Enter the 6-digit code from your app to complete setup:</p>
        
        {% if error %}
            <div class="error" role="alert">{{ error }}</div>
        {% endif %}
        
        <form method="POST">
            <input type="text" name="code" placeholder="123456" maxlength="6" required autocomplete="one-time-code">
            <button type="submit">Verify & Complete</button>
        </form>
    </main>
</body>
</html>
'''

VERIFY_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Verify Code — MaxBytes Campus</title>
    <style>
        body {
            margin: 0;
            padding: 24px;
            font-family: Arial, sans-serif;
            background: #f3f5f7;
            color: #17212b;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        main {
            width: 100%;
            max-width: 420px;
            padding: 32px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            box-sizing: border-box;
            text-align: center;
        }
        h2 {
            margin-top: 0;
            color: #075c45;
        }
        p {
            color: #555;
            font-size: 14px;
            line-height: 1.5;
            margin-bottom: 20px;
        }
        input[type="text"] {
            box-sizing: border-box;
            width: 100%;
            padding: 12px;
            border: 1px solid #aab5bf;
            border-radius: 6px;
            font-size: 20px;
            text-align: center;
            letter-spacing: 4px;
        }
        input:disabled {
            background-color: #eef2f6;
            cursor: not-allowed;
        }
        button {
            width: 100%;
            margin-top: 20px;
            padding: 12px 18px;
            border: 0;
            border-radius: 6px;
            background: #075c45;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:disabled {
            background: #aab5bf;
            cursor: not-allowed;
        }
        button:hover:not(:disabled) {
            background: #054835;
        }
        .error {
            color: #a01818;
            background: #fdf2f2;
            padding: 10px;
            border-radius: 6px;
            font-weight: bold;
            margin-bottom: 16px;
        }
    </style>
</head>
<body>
    <main>
        <h2>Two-Factor Authentication</h2>
        <p>Enter your 6-digit authenticator code to proceed.</p>
        
        {% if error %}
            <div class="error" role="alert">{{ error }}</div>
        {% endif %}
        
        <form method="POST">
            <input type="text" name="code" placeholder="123456" maxlength="6" required autocomplete="one-time-code" {% if locked %}disabled{% endif %}>
            <button type="submit" {% if locked %}disabled{% endif %}>Verify Code</button>
        </form>
        
        {% if locked %}
            <p style="margin-top: 15px; font-size: 12px;"><a href="/verify-code">Refresh page</a> to check lockout status.</p>
        {% endif %}
    </main>
</body>
</html>
'''

if __name__ == '__main__':
    init_totp_db()
    app.run(host="127.0.0.1", port=5051, debug=True)