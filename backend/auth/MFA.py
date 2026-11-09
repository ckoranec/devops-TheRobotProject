
import pyotp
import qrcode
import sqlite3

USER_DB_PATH = "user.db"
TOTP_DB_PATH = "totp.db"

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

def setup_2fa(user_id):
    init_totp_db()
    conn_user = sqlite3.connect(USER_DB_PATH)
    cursor_user = conn_user.cursor()
    cursor_user.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    result = cursor_user.fetchone()
    conn_user.close()

    if not result:
        print(f"Error: User ID {user_id} not found in database.")
        return None

    username = result[0]
    #Generate the base32 secret key
    secret = pyotp.random_base32()

    conn_totp = sqlite3.connect(TOTP_DB_PATH)
    cursor_totp = conn_totp.cursor()
    cursor_totp.execute(
        """
            INSERT OR REPLACE INTO totp_secrets (user_id, totp_secret)
            VALUES (?, ?)
        """,
        (user_id, secret),
    )
    conn_totp.commit()
    conn_totp.close()

    #Generate URL and QR code
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=username, issuer_name="Robot Project")

    print(f"=== 2FA SETUP FOR USER ID: {user_id} ({username}) ===")
    print("Scan this QR code with Google Authenticator:\n")
    qr = qrcode.QRCode()
    qr.add_data(uri)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    print("=" * 50 + "\n")

    return secret

def verify_2fa(user_id, user_input_code):
    conn_totp = sqlite3.connect(TOTP_DB_PATH)
    cursor_totp = conn_totp.cursor()
    cursor_totp.execute(
        "SELECT totp_secret FROM totp_secrets WHERE user_id = ?", (user_id,)
    )
    result = cursor_totp.fetchone()
    conn_totp.close()

    if not result or not result[0]:
        print(
            f"Error: No 2FA secret found for User ID {user_id}. Make sure it was"
            " saved to the database."
        )
        return False
    stored_secret = result[0]
    totp = pyotp.TOTP(stored_secret)

    if totp.verify(user_input_code):
    print("Success! Access granted for User ID:", user_id)
    return True
  else:
    print("Failure! Invalid or expired code.")
    return False



