import os
import sqlite3
from flask import Flask
from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)

DB_FILE = "users.db"

def init_db():
    """Creates the SQLite database and the users table if they don't exist."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """
        )
        conn.commit()


def hash_password(password: str) -> str:
    return bcrypt.generate_password_hash(password).decode("utf-8")


def check_password(hashed_password: str, plain_password: str) -> bool:
    return bcrypt.check_password_hash(hashed_password, plain_password)


# --- Database Operations ---


def register_user(username, password):
    """Inserts a new user into the SQLite table with a hashed password."""
    try:
        hashed = hash_password(password)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hashed),
            )
            conn.commit()
        return f"User '{username}' registered successfully!"
    except sqlite3.IntegrityError:
        return "Registration failed: Username already exists."


def login_user(username, password):
    """Retrieves the hash from SQLite and validates it."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        )
        row = cursor.fetchone()

    if not row:
        return "Login failed: User not found."

    stored_hash = row[0]
    if check_password(stored_hash, password):
        return "Login successful!"
    else:
        return "Login failed: Incorrect password."


# --- Run the Test Flow ---
if __name__ == "__main__":
    # Clean old test files if they exist to keep test fresh
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    print("--- 1. Initializing SQLite Database ---")
    init_db()
    print(f"Created file: {DB_FILE} locally.")

    print("\n--- 2. Registering Bob ---")
    print(register_user("bob_the_intern", "Password789!"))

    print("\n--- 3. Attempting Double Registration ---")
    print(register_user("bob_the_intern", "Password789!"))

    print("\n--- 4. Logging In (Wrong Password) ---")
    print(login_user("bob_the_intern", "WrongOne"))

    print("\n--- 5. Logging In (Correct Password) ---")
    print(login_user("bob_the_intern", "Password789!"))
