import os
import sqlite3
from faker import Faker
try:
    from .password_hashing import hash_password
except ImportError:
    from password_hashing import hash_password

# Kept next to this script so it lands in the same place wherever you run it from
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
fake = Faker()

TEST_USERNAME = "staff_test"
TEST_PASSWORD = "Robot-Test-2026!"

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

        # One fixed test user so everyone (and Card 3's attack script) can log in the same way.
        # Simulated account in a local-only database: this is not a real secret.
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
            (TEST_USERNAME, hash_password(TEST_PASSWORD)),
        )
        print(f"Test user     | Username: {TEST_USERNAME:<15} | Password: {TEST_PASSWORD}")

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

