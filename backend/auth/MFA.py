import io
import base64
import secrets
import sqlite3
import time
import os
import logging

import pyotp
import qrcode
from flask import Flask, redirect, render_template_string, request, session, url_for, abort

from seed_users import DB_FILE
from campus_login import find_identity

USER_DB_PATH = DB_FILE          
TOTP_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),"totp.db" 
)      
PENDING_SECONDS = 300           # Time allowed to enter the code
MAX_CODE_TRIES = 5

# Configure logging to write to both a file and the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),"account_activity.log"), encoding="utf-8"
            ),
        logging.StreamHandler()
    ]
)

"""
    run command in terminal first to load secret
    $env:FLASK_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
"""
app = Flask(__name__)
app.secret_key =  os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("Set FLASK_SECRET_KEY before starting the application.")

def init_totp_db():
    conn = sqlite3.connect(TOTP_DB_PATH)
    cursor = conn.cursor()
    # Server-side tracking columns for failed attempts and lockout timers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS totp_secrets (
            user_id INTEGER PRIMARY KEY,
            totp_secret TEXT NOT NULL,
            failed_attempts INTEGER DEFAULT 0,
            lockout_until REAL DEFAULT 0.0,
            confirmed INTEGER NOT NULL DEFAULT 0
        )
    """)
    try:
        cursor.execute("ALTER TABLE totp_secrets ADD COLUMN confirmed INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass  # column already exist
    conn.commit()
    conn.close()

def get_totp_record(user_id):
    init_totp_db()
    conn = sqlite3.connect(TOTP_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT totp_secret, failed_attempts, lockout_until, confirmed FROM totp_secrets WHERE user_id = ?",
        (user_id,),
    )  
    row = cursor.fetchone()
    conn.close()
    return row

def update_totp_attempts(user_id, failed_attempts, lockout_until):
    init_totp_db()
    conn = sqlite3.connect(TOTP_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE totp_secrets 
        SET failed_attempts = ?, lockout_until = ? 
        WHERE user_id = ?
    """, (failed_attempts, lockout_until, user_id))
    conn.commit()
    conn.close()

def reset_totp_attempts(user_id):
    update_totp_attempts(user_id, 0, 0.0)

def verify_2fa(user_id, user_input_code):
    row = get_totp_record(user_id)
    if not row or not row[0]:
        return False
        
    stored_secret = row[0]
    totp = pyotp.TOTP(stored_secret)
    # valid_window=1 handles minor clock drift between server and authenticator app
    return totp.verify(user_input_code, valid_window=1)

def has_totp_secret(user_id):
    row = get_totp_record(user_id)
    return row is not None and row[0] != "" and row[3] == 1

def confirm_totp_secret(user_id):
    conn = sqlite3.connect(TOTP_DB_PATH)
    conn.execute("UPDATE totp_secrets SET confirmed = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_username_by_id(user_id):
    #Helper to fetch username from users.db by user_id
    if not user_id:
        return None
    conn = sqlite3.connect(USER_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def clear_totp_db():
    #Drops and re-initializes the TOTP table to clear all stored secrets
    conn = sqlite3.connect(TOTP_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS totp_secrets")
    conn.commit()
    conn.close()
    init_totp_db()
    print("TOTP database cleared and re-initialized.")

def remove_user_totp(user_id):
    # Removes a specific user's TOTP instance from the database
    init_totp_db()
    conn = sqlite3.connect(TOTP_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM totp_secrets WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    print(f"TOTP instance removed for user_id: {user_id}")

@app.route('/')
def index():
    return render_template_string(LOGIN_HTML, error=None)


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    user = find_identity(username, password)
    
    if user:
        user_id = int(user['id'])
        session.clear()
        session['pending_mfa_user_id'] = user_id
        session['mfa_verified'] = False
        
        # Route based on whether 2FA has already been configured
        if has_totp_secret(user_id):
            return redirect(url_for('verify_code_page'))
        else:
            return redirect(url_for('setup_2fa_page'))
            
    return render_template_string(LOGIN_HTML, error="Invalid username or password.")


@app.route('/setup-2fa', methods=['GET', 'POST'])
def setup_2fa_page():
    if 'pending_mfa_user_id' not in session:
        return abort(404)

    user_id = session['pending_mfa_user_id']
    username = get_username_by_id(user_id)   # defined before any logging
    if not username:
        return abort(404)

    # Only a CONFIRMED secret blocks setup
    if has_totp_secret(user_id):
        return redirect(url_for('verify_code_page'))

    row = get_totp_record(user_id)           # may be an unconfirmed pending secret
    failed_attempts = row[1] if row else 0
    lockout_until = row[2] if row else 0.0
    current_time = time.time()

    if current_time < lockout_until:
        remaining_seconds = int(lockout_until - current_time)
        logging.warning(f"Lockout active block | set.up-2fa | user_id={user_id} ({username}) | remaining_seconds={remaining_seconds}")
        return render_template_string(SETUP_HTML, qr_base64="", secret="",
                                      error=f"Too many failed attempts. Try again in {remaining_seconds}s.", locked=True)

    if lockout_until > 0 and current_time >= lockout_until:
        reset_totp_attempts(user_id)
        failed_attempts = 0
        lockout_until = 0.0
        logging.info(f"Lockout expired & reset | setup-2fa | user_id={user_id} ({username})")

    # Reuse the pending secret if there is one; only create it once
    if row and row[0]:
        secret = row[0]
    else:
        secret = pyotp.random_base32()
        init_totp_db()
        conn = sqlite3.connect(TOTP_DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO totp_secrets (user_id, totp_secret, failed_attempts, lockout_until, confirmed) "
            "VALUES (?, ?, 0, 0.0, 0)",
            (user_id, secret),
        )
        conn.commit()
        conn.close()

    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="Robot Project")
    buffered = io.BytesIO()
    qrcode.make(uri).save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    if request.method == 'POST':
        user_input_code = (request.form.get('code') or "").strip()
        if verify_2fa(user_id, user_input_code):
            confirm_totp_secret(user_id)
            reset_totp_attempts(user_id)
            session.pop('pending_mfa_user_id', None)
            session['authenticated_user_id'] = user_id
            session['mfa_verified'] = True
            logging.info(f"2FA Setup verification success | user_id={user_id} ({username})")
            return redirect(url_for('dashboard'))

        failed_attempts += 1
        if failed_attempts >= MAX_CODE_TRIES:
            lockout_until = time.time() + 60
            update_totp_attempts(user_id, failed_attempts, lockout_until)
            logging.error(f"LOCKOUT TRIGGERED | setup-2fa | user_id={user_id} ({username}) | failed_attempts={failed_attempts}/{MAX_CODE_TRIES} | locked_for=60s")
            return render_template_string(SETUP_HTML, qr_base64=qr_base64, secret=secret,
                                          error="Too many failed attempts. Locked out for 1 minute.", locked=True)
        update_totp_attempts(user_id, failed_attempts, lockout_until)
        remaining = MAX_CODE_TRIES - failed_attempts
        logging.warning(f"2FA Setup verification failed | user_id={user_id} ({username}) | attempt {failed_attempts} of {MAX_CODE_TRIES}")
        return render_template_string(SETUP_HTML, qr_base64=qr_base64, secret=secret,
                                      error=f"Invalid code. {remaining} attempts remaining.", locked=False)

    return render_template_string(SETUP_HTML, qr_base64=qr_base64, secret=secret, error=None, locked=False)


@app.route('/verify-code', methods=['GET', 'POST'])
def verify_code_page():
    if 'pending_mfa_user_id' not in session:
        return abort(404)

    user_id = session['pending_mfa_user_id']
    if not has_totp_secret(user_id):
        return redirect(url_for('setup_2fa_page'))
    username = get_username_by_id(user_id)

    # Check server-side lockout status
    row = get_totp_record(user_id)
    failed_attempts = row[1] if row else 0
    lockout_until = row[2] if row else 0.0
    current_time = time.time()

    if current_time < lockout_until:
        remaining_seconds = int(lockout_until - current_time)
        logging.warning(f"Lockout active block | verify-code | user_id={user_id} ({username}) | remaining_seconds={remaining_seconds}")
        return render_template_string(VERIFY_HTML, error=f"Too many failed attempts. Try again in {remaining_seconds}s.", locked=True)

    if lockout_until > 0 and current_time >= lockout_until:
        reset_totp_attempts(user_id)
        failed_attempts = 0
        logging.info(f"Lockout expired & reset | verify-code | user_id={user_id} ({username})")

    if request.method == 'POST':
        user_input_code = request.form.get('code')
        
        if verify_2fa(user_id, user_input_code):
            reset_totp_attempts(user_id)
            session.pop('pending_mfa_user_id', None)
            session['authenticated_user_id'] = user_id
            session['mfa_verified'] = True
            logging.info(f"2FA verification success | user_id={user_id} ({username})")
            return redirect(url_for('dashboard'))
        else:
            failed_attempts += 1
            if failed_attempts >= MAX_CODE_TRIES:
                lockout_until = time.time() + 60
                update_totp_attempts(user_id, failed_attempts, lockout_until)
                logging.error(f"LOCKOUT TRIGGERED | verify-code | user_id={user_id} ({username}) | failed_attempts={failed_attempts}/{MAX_CODE_TRIES} | locked_for=60s")
                return render_template_string(VERIFY_HTML, error="Too many failed attempts. Locked out for 1 minute.", locked=True)
            else:
                update_totp_attempts(user_id, failed_attempts, lockout_until)
                remaining = MAX_CODE_TRIES - failed_attempts
                logging.warning(f"2FA verification failed | user_id={user_id} ({username}) | attempt {failed_attempts} of {MAX_CODE_TRIES}")
                return render_template_string(VERIFY_HTML, error=f"Invalid code. {remaining} attempts remaining.", locked=False)

    return render_template_string(VERIFY_HTML, error=None, locked=False)


@app.route('/dashboard')
def dashboard():
    if not session.get('mfa_verified') or 'authenticated_user_id' not in session:
        return abort(404)
        
    return """
        <h2>Welcome to your Secure Dashboard!</h2>
        <p>You have successfully passed both password authentication and 2FA.</p>
        <a href="/logout">Logout</a>
    """


@app.route('/logout')
def logout():
    user_id = session.get('authenticated_user_id')
    if user_id:
        username = get_username_by_id(user_id)
    else:
        logging.warning("Unknown user logout attempted without active session")
        username = "Unknown"
    session.clear()
    logging.info(f"User logout | user_id={user_id} ({username})")
    return redirect(url_for('index'))


@app.route('/reset-2fa/<int:target_user_id>')
def reset_2fa(target_user_id):
    target_username = get_username_by_id(target_user_id)
    if not app.debug:
        logging.warning(f"Unauthorized reset attempt in non-debug mode | target_user_id={target_user_id} | IP={request.remote_addr}")
        return abort(403)
        
    current_user_id = session.get('authenticated_user_id') or session.get('pending_mfa_user_id')
    current_username= get_username_by_id(current_user_id)
    if not current_user_id:
        logging.warning(f"Unauthenticated reset attempt | target_user_id={target_user_id} | IP={request.remote_addr}")
        return abort(403)
        
    # Prevent users from resetting someone else's 2FA account
    if current_user_id != target_user_id:
        logging.error(f"SECURITY VIOLATION: Cross-user 2FA reset attempt blocked! | actor_id={current_user_id} ({current_username}) tried to reset target_user_id={target_user_id}")
        return abort(403)

    remove_user_totp(target_user_id)
    session.clear()
    session['pending_mfa_user_id'] = target_user_id
    session['mfa_verified'] = False

    logging.info(f"2FA reset successful | user_id={target_user_id} ({target_username}) cleared their own 2FA instance")
    return redirect(url_for('setup_2fa_page'))


# --- HTML & CSS TEMPLATES ---
LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
    <h2>Staff Login</h2>
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
    <title>Setup 2FA</title>
    <style>
        body { margin: 0; padding: 24px; font-family: Arial, sans-serif; background: #f3f5f7; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        main { width: 100%; max-width: 480px; padding: 32px; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); text-align: center; box-sizing: border-box; }
        h2 { color: #075c45; margin-top: 0; }
        p { color: #555; font-size: 14px; text-align: left; line-height: 1.5; }
        input[type="text"] { width: 100%; padding: 12px; border: 1px solid #aab5bf; border-radius: 6px; font-size: 18px; text-align: center; letter-spacing: 4px; box-sizing: border-box; }
        input:disabled { background: #eef2f6; cursor: not-allowed; }
        button { width: 100%; margin-top: 20px; padding: 12px; border: 0; border-radius: 6px; background: #075c45; color: white; font-size: 16px; font-weight: bold; cursor: pointer; }
        button:disabled { background: #aab5bf; cursor: not-allowed; }
        .error { color: #a01818; background: #fdf2f2; padding: 10px; border-radius: 6px; font-weight: bold; margin-bottom: 16px; text-align: center; }
        code { background: #eef2f6; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 13px; word-break: break-all; }
        .qr-container { margin: 16px 0; padding: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; display: inline-block; }
        img { max-width: 160px; height: auto; display: block; margin: 0 auto; }
        hr { border: 0; border-top: 1px solid #d5dce2; margin: 20px 0; }
    </style>
</head>
<body>
    <main>
        <h2>Set Up Two-Factor Authentication</h2>
        {% if secret %}
            <p><strong>Step 1:</strong> Scan this QR code with your app:</p>
            <div class="qr-container">
                <img src="data:image/png;base64,{{ qr_base64 }}" alt="QR Code">
            </div>
            <p style="text-align: center; font-size: 13px;">Manual Code: <code>{{ secret }}</code></p>
            <hr>
        {% endif %}
        <p><strong>Step 2:</strong> Enter the 6-digit code:</p>
        {% if error %}<div class="error" role="alert">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="text" name="code" placeholder="123456" maxlength="6" required autocomplete="one-time-code" {% if locked %}disabled{% endif %}>
            <button type="submit" {% if locked %}disabled{% endif %}>Verify & Complete</button>
        </form>
        {% if locked %}
            <p style="margin-top:15px; font-size:12px; text-align: center;"><a href="/setup-2fa">Refresh page</a> to check lockout status.</p>
        {% endif %}
    </main>
</body>
</html>
'''

VERIFY_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Verify Code</title>
    <style>
        body { margin: 0; padding: 24px; font-family: Arial, sans-serif; background: #f3f5f7; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        main { width: 100%; max-width: 420px; padding: 32px; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); text-align: center; box-sizing: border-box; }
        h2 { color: #075c45; margin-top: 0; }
        p { color: #555; font-size: 14px; margin-bottom: 20px; }
        input[type="text"] { width: 100%; padding: 12px; border: 1px solid #aab5bf; border-radius: 6px; font-size: 20px; text-align: center; letter-spacing: 4px; box-sizing: border-box; }
        input:disabled { background: #eef2f6; cursor: not-allowed; }
        button { width: 100%; margin-top: 20px; padding: 12px; border: 0; border-radius: 6px; background: #075c45; color: white; font-size: 16px; font-weight: bold; cursor: pointer; }
        button:disabled { background: #aab5bf; cursor: not-allowed; }
        .error { color: #a01818; background: #fdf2f2; padding: 10px; border-radius: 6px; font-weight: bold; margin-bottom: 16px; }
    </style>
</head>
<body>
    <main>
        <h2>Two-Factor Authentication</h2>
        <p>Enter your 6-digit authenticator code:</p>
        {% if error %}<div class="error" role="alert">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="text" name="code" placeholder="123456" maxlength="6" required autocomplete="one-time-code" {% if locked %}disabled{% endif %}>
            <button type="submit" {% if locked %}disabled{% endif %}>Verify</button>
        </form>
        {% if locked %}
            <p style="margin-top:15px; font-size:12px;"><a href="/verify-code">Refresh page</a> to check lockout status.</p>
        {% endif %}
    </main>
</body>
</html>
'''

if __name__ == '__main__':
    init_totp_db()
    app.run(host="127.0.0.1", port=5051, debug=True)