import sqlite3
from faker import Faker
from flask import Flask
from flask_bcrypt import Bcrypt

# Re-use your configuration
app = Flask(__name__)
bcrypt = Bcrypt(app)
DB_FILE = "users.db"
fake = Faker()


def hash_password(password: str) -> str:
    return bcrypt.generate_password_hash(password).decode("utf-8")


def seed_database(num_users=20):
    """Generates fake users and inserts them into the SQLite table."""
    print(f"--- Generating {num_users} Simulation Users ---")

    # Connect to the database
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Ensure table exists before seeding
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """
        )

        for _ in range(num_users):
            # Generate a realistic fake username and password
            username = fake.user_name()
            plain_password = fake.password(length=12)

            # Hash the password safely using Bcrypt
            hashed_pw = hash_password(plain_password)

            try:
                cursor.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, hashed_pw),
                )
                # Print out the credentials so you can use them for login testing
                print(f"User Created | Username: {username:<15} | Plain Text Password: {plain_password}")
            except sqlite3.IntegrityError:
                # Skip if Faker randomly generates a duplicate username
                continue

        conn.commit()
    print("\n--- Seeding Complete! 'users.db' is ready for simulation. ---")


if __name__ == "__main__":
    # Generate 15 simulation profiles by default
    seed_database(15)

