
import os
import sqlite3

# Locate users.db in the same directory as this script.
DB_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "users.db"
)


def get_user_by_username(username):
    """Retrieve a user from the database by username."""

    conn = sqlite3.connect(DB_FILE)

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,)
        )

        user = cursor.fetchone()
        return user

    finally:
        conn.close()

def update_user_password(username, new_password_hash):
    # Update a user's stored password hash

    conn = sqlite3.connect(DB_FILE)

    try:
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (new_password_hash, username)
        )

        updated_rows = cursor.rowcount
        conn.commit()

        return updated_rows == 1

    finally:
        conn.close()


if __name__ == "__main__":
    user = get_user_by_username("staff_test")

    if user:
        print("User found!")
        print("ID:", user[0])
        print("Username:", user[1])
        print("Password hash:", user[2])
    else:
        print("User not found.")
