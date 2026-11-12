# 2026-11-11 — David Noyes — Card 4 fake campus directory.
# Learning version: comments explain each executable line.

import os  # Read environment variables supplied when starting the application.

from backend.auth.password_hashing import hash_password, verify_password  # Reuse the team's password functions.


def build_directory(staff_password, student_password):  # Receive the two fake campus passwords.
    if not staff_password or not student_password:  # Require both passwords to be present.
        raise ValueError("Both fake campus passwords are required.")  # Stop if setup is incomplete.

    staff_account = {  # Create the fake university staff account.
        "campus_id": "CAMPUS-1001",  # Keep this ID unchanged when the username changes.
        "username": "campus_staff",  # Set the account's login name.
        "name": "Demo Staff",  # Use a fictional display name.
        "affiliation": "staff",  # Describe university affiliation, not staff-site permissions.
        "password_hash": hash_password(staff_password),  # Store a hash instead of the password.
    }  # Finish the staff account.

    student_account = {  # Create the fake university student account.
        "campus_id": "CAMPUS-2001",  # Give the student a different stable ID.
        "username": "campus_student",  # Set the student's login name.
        "name": "Demo Student",  # Use a fictional display name.
        "affiliation": "student",  # Identify the account as a university student.
        "password_hash": hash_password(student_password),  # Hash the student's password.
    }  # Finish the student account.

    directory = {  # Organize the accounts so each username can be looked up.
        "campus_staff": staff_account,  # Connect the staff username to its account.
        "campus_student": student_account,  # Connect the student username to its account.
    }  # Finish the directory.

    return directory  # Give the completed directory back to the caller.


def directory_from_environment():  # Load the running application's directory.
    staff_password = os.environ.get("CAMPUS_FAKE_STAFF_PASSWORD", "")  # Read the staff password or an empty default.
    student_password = os.environ.get("CAMPUS_FAKE_STUDENT_PASSWORD", "")  # Read the student password or an empty default.

    if not staff_password or not student_password:  # Detect missing setup values.
        raise RuntimeError("Set CAMPUS_FAKE_STAFF_PASSWORD and CAMPUS_FAKE_STUDENT_PASSWORD.")  # Name the missing settings without revealing values.

    directory = build_directory(staff_password, student_password)  # Build the accounts using hashed passwords.
    return directory  # Return the independent campus directory.


def authenticate(directory, username, password):  # Check a submitted campus login.
    account = directory.get(username)  # Get the account or None if the username is missing.

    if account is None:  # Handle an unknown username.
        return None  # Report authentication failure.

    password_matches = verify_password(account["password_hash"], password)  # Check the submitted password using the shared function.

    if not password_matches:  # Handle a password that does not match.
        return None  # Return the same failure result as an unknown username.

    identity = {  # Select the identity fields that may leave the directory.
        "campus_id": account["campus_id"],  # Include the permanent campus ID.
        "username": account["username"],  # Include the current username.
        "name": account["name"],  # Include the display name.
        "affiliation": account["affiliation"],  # Include affiliation without assigning a staff-site role.
    }  # Exclude the password and its hash.

    return identity  # Return verified identity information.


def test_staff_and_student_accounts():  # Test both campus account types.
    directory = build_directory("Local-Staff-Test-Only!", "Local-Student-Test-Only!")  # Use synthetic test passwords.

    staff = authenticate(directory, "campus_staff", "Local-Staff-Test-Only!")  # Authenticate the staff campus account.
    student = authenticate(directory, "campus_student", "Local-Student-Test-Only!")  # Authenticate the student campus account.

    assert staff is not None  # Require successful campus staff authentication.
    assert student is not None  # Require successful campus student authentication.
    assert staff["campus_id"] == "CAMPUS-1001"  # Check the staff account's stable ID.
    assert staff["affiliation"] == "staff"  # Check its affiliation.
    assert student["campus_id"] == "CAMPUS-2001"  # Check the student's stable ID.
    assert student["affiliation"] == "student"  # Check its affiliation.
    assert "password_hash" not in staff  # Confirm the staff identity excludes its hash.
    assert "password_hash" not in student  # Confirm the student identity excludes its hash.
    assert "role" not in staff  # Confirm campus authentication grants no staff-site role.
    assert "role" not in student  # Confirm the student identity also grants no role.


def test_invalid_credentials():  # Test failed authentication.
    directory = build_directory("Local-Staff-Test-Only!", "Local-Student-Test-Only!")  # Create isolated test accounts.

    wrong_password = authenticate(directory, "campus_staff", "wrong")  # Try an incorrect password.
    unknown_account = authenticate(directory, "missing", "wrong")  # Try an unknown username.

    assert wrong_password is None  # Require the wrong password to fail.
    assert unknown_account is None  # Require the unknown account to fail.


def test_username_change_preserves_campus_id():  # Test an account rename.
    directory = build_directory("Local-Staff-Test-Only!", "Local-Student-Test-Only!")  # Create an in-memory test directory.

    account = directory["campus_staff"]  # Obtain the existing staff account.
    del directory["campus_staff"]  # Remove only the old dictionary lookup entry.
    account["username"] = "renamed_staff"  # Change the username without changing the campus ID.
    directory["renamed_staff"] = account  # Store the same account under its new username.

    identity = authenticate(directory, "renamed_staff", "Local-Staff-Test-Only!")  # Sign in under the new name.
    old_login = authenticate(directory, "campus_staff", "Local-Staff-Test-Only!")  # Try the removed name.

    assert identity is not None  # Require the renamed account to work.
    assert identity["campus_id"] == "CAMPUS-1001"  # Require its campus identity to stay unchanged.
    assert old_login is None  # Require the old login name to fail.

    # 2026-11-12 — David Noyes — Add campus table setup and an isolated test.


def create_campus_table(database_path):
    # Open an existing database for writing without creating a missing database.
    import sqlite3
    from pathlib import Path

    database_uri = Path(database_path).resolve().as_uri() + "?mode=rw"
    connection = sqlite3.connect(database_uri, uri=True)

    # Create only the campus table, then close the connection even if SQL fails.
    try:
        connection.execute("""
               CREATE TABLE IF NOT EXISTS campus_accounts (
                   campus_id TEXT PRIMARY KEY NOT NULL,
                   username TEXT UNIQUE NOT NULL,
                   name TEXT NOT NULL,
                   affiliation TEXT NOT NULL
                       CHECK (affiliation IN ('staff', 'student')),
                   password_hash TEXT NOT NULL
               )
           """)
        connection.commit()
    finally:
        connection.close()


def test_create_campus_table_preserves_staff(tmp_path):
    # Build a disposable database containing one fictional staff record.
    import sqlite3

    database_path = tmp_path / "campus_table_test.db"
    connection = sqlite3.connect(database_path)

    try:
        connection.execute("""
               CREATE TABLE users (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   username TEXT UNIQUE NOT NULL,
                   password_hash TEXT NOT NULL
               )
           """)
        connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("staff_fixture", "test-placeholder-not-a-login-hash"),
        )
        connection.commit()
    finally:
        connection.close()

    # Running setup twice must succeed without removing the existing staff row.
    create_campus_table(database_path)
    create_campus_table(database_path)

    # Inspect the resulting tables in the disposable database.
    connection = sqlite3.connect(database_path)
    try:
        columns = connection.execute(
            "PRAGMA table_info(campus_accounts)"
        ).fetchall()
        staff_rows = connection.execute(
            "SELECT id, username, password_hash FROM users"
        ).fetchall()
        campus_count = connection.execute(
            "SELECT COUNT(*) FROM campus_accounts"
        ).fetchone()[0]
    finally:
        connection.close()

    # Confirm the campus columns exist, the table is empty, and staff data survived.
    column_names = [column[1] for column in columns]
    assert column_names == [
        "campus_id",
        "username",
        "name",
        "affiliation",
        "password_hash",
    ]
    assert campus_count == 0
    assert staff_rows == [
        (1, "staff_fixture", "test-placeholder-not-a-login-hash")
    ]

    # 2026-11-12 — David Noyes — Seed independent campus accounts safely.


def seed_campus_accounts(database_path, staff_password, student_password):
    # Require both passwords before making any database changes.
    import sqlite3
    from pathlib import Path

    if not staff_password or not student_password:
        raise ValueError("Both fake campus passwords are required.")

    # Prepare the campus table in the existing database.
    create_campus_table(database_path)
    database_uri = Path(database_path).resolve().as_uri() + "?mode=rw"
    connection = sqlite3.connect(database_uri, uri=True)

    # Define initial identities; staff-site permissions belong to Colin's mapping.
    accounts = [
        ("CAMPUS-1001", "campus_staff", "Demo Staff", "staff", staff_password),
        ("CAMPUS-2001", "campus_student", "Demo Student", "student", student_password),
    ]

    # Add missing identities without changing accounts that already exist.
    added_count = 0
    try:
        for campus_id, username, name, affiliation, password in accounts:
            existing_account = connection.execute(
                "SELECT campus_id FROM campus_accounts WHERE campus_id = ?",
                (campus_id,),
            ).fetchone()

            if existing_account is not None:
                continue

            password_hash = hash_password(password)
            connection.execute(
                """
                INSERT INTO campus_accounts
                    (campus_id, username, name, affiliation, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (campus_id, username, name, affiliation, password_hash),
            )
            added_count += 1

        connection.commit()
    except Exception:
        # Undo this call's account inserts if any insert or hashing operation fails.
        connection.rollback()
        raise
    finally:
        connection.close()

    # Tell the caller how many new accounts were inserted.
    return added_count


def seed_campus_accounts_from_environment(database_path):
    # Read setup passwords without placing their values in source code or output.
    staff_password = os.environ.get("CAMPUS_FAKE_STAFF_PASSWORD", "")
    student_password = os.environ.get("CAMPUS_FAKE_STUDENT_PASSWORD", "")

    if not staff_password or not student_password:
        raise RuntimeError(
            "Set CAMPUS_FAKE_STAFF_PASSWORD and CAMPUS_FAKE_STUDENT_PASSWORD."
        )

    return seed_campus_accounts(
        database_path, staff_password, student_password
    )


def test_seed_campus_accounts_preserves_existing_data(tmp_path):
    # Create a disposable database and a staff record unrelated to campus accounts.
    import sqlite3

    database_path = tmp_path / "campus_seed_test.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)"
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?)",
            (1, "existing_staff"),
        )
        connection.commit()
    finally:
        connection.close()

    # Supply synthetic passwords used only by this automated test.
    staff_password = "Test-Staff-Only!"
    student_password = "Test-Student-Only!"
    added_count = seed_campus_accounts(
        database_path, staff_password, student_password
    )

    # Repeat setup with different inputs; existing passwords must remain unchanged.
    repeated_count = seed_campus_accounts(
        database_path, "Different-Staff-Test!", "Different-Student-Test!"
    )

    # Read the stored results from the temporary database.
    connection = sqlite3.connect(database_path)
    try:
        campus_rows = connection.execute(
            """
            SELECT campus_id, username, name, affiliation, password_hash
            FROM campus_accounts
            ORDER BY campus_id
            """
        ).fetchall()
        staff_rows = connection.execute(
            "SELECT id, username FROM users"
        ).fetchall()
    finally:
        connection.close()

    # Verify the account identities, affiliations, and preservation of staff data.
    assert added_count == 2
    assert repeated_count == 0
    assert len(campus_rows) == 2
    assert campus_rows[0][:4] == (
        "CAMPUS-1001", "campus_staff", "Demo Staff", "staff"
    )
    assert campus_rows[1][:4] == (
        "CAMPUS-2001", "campus_student", "Demo Student", "student"
    )
    assert staff_rows == [(1, "existing_staff")]

    # Verify hashing and prove repeated setup did not reset the original passwords.
    assert campus_rows[0][4] != staff_password
    assert campus_rows[1][4] != student_password
    assert verify_password(campus_rows[0][4], staff_password)
    assert verify_password(campus_rows[1][4], student_password)
    assert not verify_password(campus_rows[0][4], "Different-Staff-Test!")
    assert not verify_password(campus_rows[1][4], "Different-Student-Test!")


def test_campus_seed_requires_environment_passwords(tmp_path, monkeypatch):
    # Remove setup variables only within this test, regardless of laptop settings.
    import pytest

    monkeypatch.delenv("CAMPUS_FAKE_STAFF_PASSWORD", raising=False)
    monkeypatch.delenv("CAMPUS_FAKE_STUDENT_PASSWORD", raising=False)
    database_path = tmp_path / "must_not_be_created.db"

    # Missing passwords must fail before creating or opening a database.
    with pytest.raises(RuntimeError, match="CAMPUS_FAKE_STAFF_PASSWORD"):
        seed_campus_accounts_from_environment(database_path)

    assert not database_path.exists()