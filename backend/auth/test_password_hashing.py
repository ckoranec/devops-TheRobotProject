from backend.auth.password_hashing import hash_password, verify_password

def test_password_hashing():
    password = "Robot-Test-2026!"
    hashed = hash_password(password)

    assert verify_password(hashed, password) is True
    assert verify_password(hashed, "WrongPassword") is False