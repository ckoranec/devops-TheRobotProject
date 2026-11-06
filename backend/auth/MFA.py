
import pyotp
import qrcode
import sqlite3

DB_PATH = "user.db"

def setup_2fa(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch the username associated with this user ID for the QR label
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close() 

    if not result:
        print(f"Error: User ID {user_id} not found in database.")
        return None

    username = result[0]
    #Generate the base32 secret key
    secret = pyotp.random_base32()

    #Generate URL and QR code
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=username, issuer_name="My Python App")

    print(f"=== 2FA SETUP FOR USER ID: {user_id} ({username}) ===")
    print("Scan this QR code with Google Authenticator:\n")
    qr = qrcode.QRCode()
    qr.add_data(uri)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    print("=" * 50 + "\n")

    return secret

def verify_2fa(user_id, user_input_code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor(

    cursor.execute("SELECT totp_secret FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()

    if not result or not result[0]:
        print(
            f"Error: No 2FA secret found for User ID {user_id}. Make sure it was"
            " saved to the database."
        )
        return False
    stored_secret = result[0]
    totp = pyotp.TOTP(stored_secret)



