
import os
import sqlite3
import tempfile

import database
from password_hashing import hash_password, verify_password

# Creates a temporary database that will be deleted after testing
with tempfile.TemporaryDirectory() as temp_folder:
    test_db = os.path.join(temp_folder, "test_users.db")

    # Direct the database helper to our temporary database
    original_db = database.DB_FILE
    database.DB_FILE = test_db

    try:
        conn = sqlite3.connect(test_db)
        conn.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, "
            "username TEXT UNIQUE, password_hash TEXT)"
        )
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("recovery_test", hash_password("OldPassword123!"))
        )
        conn.commit()
        conn.close()

        # Generate a bcrypt hash for the replacement password
        new_hash = hash_password("NewPassword456!")

        # Call the function that was just added
        updated = database.update_user_password("recovery_test", new_hash)

        # Retrieve the account to check and verify the result
        user = database.get_user_by_username("recovery_test")

        print("Password update succeeded:", updated)
        print("New password verified:", verify_password(user[2], "NewPassword456!"))
        print("Old password rejected:", not verify_password(user[2], "OldPassword123!"))

    finally:
        database.DB_FILE = original_db
