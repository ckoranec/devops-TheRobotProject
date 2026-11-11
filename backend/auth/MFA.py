import io
import base64
import secrets
import sqlite3
import time

import pyotp
import qrcode
from flask import Flask, redirect, render_template_string, request, session, url_for, abort

from seed_users import DB_FILE
from campus_login import find_identity

USER_DB_PATH = DB_FILE          
TOTP_DB_PATH = "totp.db"       
PENDING_SECONDS = 300           # Time allowed to enter the code
MAX_CODE_TRIES = 5

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

def init_totp_db():
    conn = sqlite3.connect(TOTP_DB_PATH)
    cursor = conn.cursor()
    # Server-side tracking columns for failed attempts and lockout timers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS totp_secrets (
            user_id INTEGER PRIMARY KEY,
            totp_secret TEXT NOT NULL,
            failed_attempts INTEGER DEFAULT 0,
            lockout_until REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()

def get_totp_record(user_id):
    init_totp_db()
    conn = sqlite3.connect(TOTP_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT totp_secret, failed_attempts, lockout_until FROM totp_secrets WHERE user_id = ?", (user_id,))
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
    return row is not None and row[0] != ""

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
        session['pending_user_id'] = user_id
        
        # Route based on whether 2FA has already been configured
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

    # Block users who already have a secret from resetting via setup URL
    if has_totp_secret(user_id):
        return redirect(url_for('verify_code_page'))

    # Check server-side lockout status
    row = get_totp_record(user_id)
    failed_attempts = row[1] if row else 0
    lockout_until = row[2] if row else 0.0
    current_time = time.time()

    if current_time < lockout_until:
        remaining_seconds = int(lockout_until - current_time)
        return render_template_string(SETUP_HTML, qr_base64="", secret="", error=f"Too many failed attempts. Try again in {remaining_seconds}s.", locked=True)

    if lockout_until > 0 and current_time >= lockout_until:
        reset_totp_attempts(user_id)
        failed_attempts = 0

    # Fetch username for provisioning URI
    conn_user = sqlite3.connect(USER_DB_PATH)
    cursor_user = conn_user.cursor()
    cursor_user.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    result = cursor_user.fetchone()
    conn_user.close()
    
    if not result:
        return abort(404)
        
    username = result[0]
    
    # Generate new secret and save it to DB with initial attempt tracking
    secret = pyotp.random_base32()
    init_totp_db()
    conn_totp = sqlite3.connect(TOTP_DB_PATH)
    cursor_totp = conn_totp.cursor()
    cursor_totp.execute(
        "INSERT OR REPLACE INTO totp_secrets (user_id, totp_secret, failed_attempts, lockout_until) VALUES (?, ?, ?, ?)",
        (user_id, secret, failed_attempts, lockout_until),
    )
    conn_totp.commit()
    conn_totp.close()

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=username, issuer_name="Robot Project")

    qr_img = qrcode.make(uri)
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    if request.method == 'POST':
        user_input_code = request.form.get('code')
        if verify_2fa(user_id, user_input_code):
            reset_totp_attempts(user_id)
            session.pop('pending_user_id', None)
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
        else:
            failed_attempts += 1
            if failed_attempts >= MAX_CODE_TRIES:
                lockout_until = time.time() + 60
                update_totp_attempts(user_id, failed_attempts, lockout_until)
                return render_template_string(SETUP_HTML, qr_base64=qr_base64, secret=secret, error="Too many failed attempts. Locked out for 1 minute.", locked=True)
            else:
                update_totp_attempts(user_id, failed_attempts, lockout_until)
                remaining = MAX_CODE_TRIES - failed_attempts
                return render_template_string(SETUP_HTML, qr_base64=qr_base64, secret=secret, error=f"Invalid code. {remaining} attempts remaining.", locked=False)

    return render_template_string(SETUP_HTML, qr_base64=qr_base64, secret=secret, error=None, locked=False)


@app.route('/verify-code', methods=['GET', 'POST'])
def verify_code_page():
    if 'pending_user_id' not in session:
        return abort(404)

    user_id = session['pending_user_id']

    # Check server-side lockout status
    row = get_totp_record(user_id)
    failed_attempts = row[1] if row else 0
    lockout_until = row[2] if row else 0.0
    current_time = time.time()

    if current_time < lockout_until:
        remaining_seconds = int(lockout_until - current_time)
        return render_template_string(VERIFY_HTML, error=f"Too many failed attempts. Try again in {remaining_seconds}s.", locked=True)

    if lockout_until > 0 and current_time >= lockout_until:
        reset_totp_attempts(user_id)
        failed_attempts = 0

    if request.method == 'POST':
        user_input_code = request.form.get('code')
        
        if verify_2fa(user_id, user_input_code):
            reset_totp_attempts(user_id)
            session.pop('pending_user_id', None)
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
        else:
            failed_attempts += 1
            if failed_attempts >= MAX_CODE_TRIES:
                lockout_until = time.time() + 60
                update_totp_attempts(user_id, failed_attempts, lockout_until)
                return render_template_string(VERIFY_HTML, error="Too many failed attempts. Locked out for 1 minute.", locked=True)
            else:
                update_totp_attempts(user_id, failed_attempts, lockout_until)
                remaining = MAX_CODE_TRIES - failed_attempts
                return render_template_string(VERIFY_HTML, error=f"Invalid code. {remaining} attempts remaining.", locked=False)

    return render_template_string(VERIFY_HTML, error=None, locked=False)


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return abort(404)
        
    return """
        <h2>Welcome to your Secure Dashboard!</h2>
        <p>You have successfully passed both password authentication and 2FA.</p>
        <a href="/logout">Logout</a>
    """


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/reset-2fa/<int:target_user_id>')
def reset_2fa(target_user_id):
    if not app.debug:
        return abort(403)
        
    current_user_id = session.get('user_id') or session.get('pending_user_id')
    if not current_user_id:
        return abort(403)
        
    # Prevent users from resetting someone else's 2FA account
    if current_user_id != target_user_id:
        return abort(403)

    remove_user_totp(target_user_id)
    session.clear()
    session['pending_user_id'] = target_user_id
    
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