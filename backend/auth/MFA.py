
import pyotp
import qrcode

#Generate a random base32 secret key
secret = pyotp.random_base32()

#Initialize the TOTP object
totp = pyotp.TOTP(secret)

account_name = "Abhishek"
app_name = "GMU Delivery"
uri = totp.provisioning_uri(name=account_name, issuer_name=app_name)

#Display a scannable QR code directly in the terminal
print("--- SCAN THIS QR CODE WITH GOOGLE AUTHENTICATOR ---")
qr = qrcode.QRCode()
qr.add_data(uri)
qr.make(fit=True)
qr.print_ascii(invert=True)  # Inverted renders nicely on dark terminal themes
print("---------------------------------------------------\n")

current_code = totp.now()
filename = "sms.txt"

with open(filename, "w") as f:
    f.write(f"Your Google Authenticator verification code is: {current_code}\n")

print(f"[SMS Simulator] Current code '{current_code}' written to '{filename}'.\n")

user_input = input("Enter the 6-digit code from Google Authenticator or your file: ")

if totp.verify(user_input):
    print("Success! Access granted.")
else:
    print("Failure! Invalid or expired code.")