import string
from seed_users import password_set_at
from datetime import datetime, timedelta
import user.db
from webauthn import (
    generate_authentication_options, verify_authentication_response, options_to_json)
from webauthn.helpers.structs import UserVerificationRequirement
 
RP_ID = "local"
ORIGIN = "http://localhost:8000"
 
BLOCKED_PASSWORDS = {
    "Password#1",
    "Password@123",
    "Admin$2026",
    "12345678Ab#",
    "Qwerty#9",
    "LetMeIn@7",
    "Welcome1$",
    "Demo%2026",
    "AbcPassword@123",
    "NoPasswordNeeded#1",
    "123Abc$",
}
 
STAFF = {
    "jkertgate",
    "cbowie",
    "dnoyes",
    "apoudyal",
    "smoskowitz",
    "cwood",
    "rob",
}
 
AUTH_OPTIONS = {
    "fingerprint",
    "face",
    "hardware token",
    "webauthn",
    "skip",
}
 
def timeout()
    PASSWORD_LIFETIME = timedelta(days=90)
    password_set_at = datetime.now()
    return datetime.now() > password_set_at + PASSWORD_LIFETIME
 
def password_expired():
    if timeout():
        return False
 
def is_password_blocked(passwd, blocklist: set) -> bool:
 
  for blocked in blocklist:
    if blocked in password.lower():
      return True
  return False
 
def password_check(passwd):
    SpecialSym = ['!','$', '@', '#', '%', '^', '&', '*']
    val = True
 
    if password_exipired() = False
	print("Password expired.")
	val = False
 
    if is_password_blocked(passwd) = true
	print("password is blocked")
	val = False
 
    if len(passwd) < 6:
        print('Length should be at least 6')
        val = False
 
    if len(passwd) > 20:
        print('Length should not be greater than 20')
        val = False
 
    if not any(char.isdigit() for char in passwd):
        print('Password should have at least one numeral')
        val = False
 
    if not any(char.isupper() for char in passwd):
        print('Password should have at least one uppercase letter')
        val = False
 
    if not any(char.islower() for char in passwd):
        print('Password should have at least one lowercase letter')
        val = False
 
    if not any(char in SpecialSym for char in passwd):
        print('Password should have at least one of the symbols $@#%')
        val = False
 
    return val
 
def webauthn_check(username):
    val = True
    # placeholder: public key + sign count saved when the user registered their device
    credential = user.db.get_credential(username)
 
    options = generate_authentication_options(
        rp_id=RP_ID,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    print("send this to the browser:")
    print(options_to_json(options))
    response = input("paste the browser response ")
 
    try:
        verify_authentication_response(
            credential=response,
            expected_challenge=options.challenge,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=credential["public_key"],
            credential_current_sign_count=credential["sign_count"],
            require_user_verification=True,
        )
    except Exception:
        print('WebAuthn response could not be verified')
        val = False
 
    return val
 
def second_factor_check(option, username):
    val = True
 
    if option.lower() not in AUTH_OPTIONS:
        print('Option should be fingerprint, face, hardware token, webauthn, or skip')
        val = False
 
    if option.lower() == "webauthn" and not webauthn_check(username):
        print('WebAuthn check failed')
        val = False
 
    return val
 
def main():
    MAX_ATTEMPTS = 6
    failed = 0
    user = input("input username")
    
    if user = [row[0] for row in -userdatabase- not in STAFF]
	print("user is not staff")
	failed += 1
 
    print("Biometric or hardware token options available.")
    option = input("choose fingerprint, face, hardware token, webauthn, or skip ")
    biometric_passed = False
 
    if option.lower() == "skip":
        print("Second factor skipped")
    elif second_factor_check(option, user):
        print("Second factor accepted")
        if option.lower() == "webauthn":
            biometric_passed = True
    else:
        print("Invalid second factor !!")
        failed += 1
 
    if biometric_passed:
        print("Password check skipped")
    else:
        passwd = input("input password ")
        if password_check(passwd):
            print("Password is valid")
        else:
            print("Invalid Password !!")
            failed += 1
