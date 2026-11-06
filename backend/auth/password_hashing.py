from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

def hash_password(password):
    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
    return hashed_password

def verify_password(stored_hash, candidate_password):
    return bcrypt.check_password_hash(stored_hash, candidate_password)
