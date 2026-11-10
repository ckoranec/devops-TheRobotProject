import secrets
import hashlib
from datetime import datetime

otp = f"{secrets.randbelow(1_000_000):06d}"
stored_hash = hashlib.sha256(otp.encode()).hexdigest()

print("Stored hash:", stored_hash)

filename = "recovery_notice.txt"
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

notice = f"""Recovery Code Notice
=====================
Your 6-digit recovery code is: {otp}

Please keep this code secure. It will not be shown again.
Only the hashed version has been stored.
"""

with open(filename, "w", encoding="utf-8") as f:
    f.write(notice)

print(f"Recovery notice written to: {filename}")