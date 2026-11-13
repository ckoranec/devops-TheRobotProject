import secrets
import hashlib
import smtplib
from email.message import EmailMessage

otp = f"{secrets.randbelow(1_000_000):06d}"
stored_hash = hashlib.sha256(otp.encode()).hexdigest()

print("Stored hash:", stored_hash)

def send_otp_email(recipient, otp_code):
    # --- Change these ---
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = "maxx.byte.recovery@gmail.com"
    APP_PASSWORD = "odfy nrwu ibnq ccdt"

    msg = EmailMessage()
    msg["Subject"] = "Your verification code"
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient
    msg.set_content(f"Your 6-digit code is: {otp_code}\n\nIt expires soon. Do not share it.")

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
    print(f"OTP sent to {recipient}")

send_otp_email("maxx.byte.notifications@gmail.com", otp)