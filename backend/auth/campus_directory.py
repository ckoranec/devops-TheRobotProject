# 2026-11-16 — David Noyes — Card 4 database-backed campus directory.
# Campus identities are separate from staff accounts and do not grant staff roles.

import os
import sqlite3
from pathlib import Path

from backend.auth.password_hashing import hash_password, verify_password


def create_campus_table(database_path):
    # Require an existing database so a mistaken path cannot create another one.
    database_uri = Path(database_path).resolve().as_uri() + "?mode=rw"
    connection = sqlite3.connect(database_uri, uri=True)

    try:
        # Create only the campus table; preserve existing tables and records.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS campus_accounts (
                campus_id TEXT PRIMARY KEY NOT NULL,
                username TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                affiliation TEXT NOT NULL
                    CHECK (affiliation IN ('staff', 'student')),
                password_hash TEXT NOT NULL
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def seed_campus_accounts(database_path, staff_password, student_password):
    # Reject incomplete setup before making database changes.
    if not staff_password or not student_password:
        raise ValueError("Both fake campus passwords are required.")

    create_campus_table(database_path)
    database_uri = Path(database_path).resolve().as_uri() + "?mode=rw"
    connection = sqlite3.connect(database_uri, uri=True)

    # These stable campus IDs identify people independently of their usernames.
    accounts = [
        ("CAMPUS-1001", "campus_staff", "Demo Staff", "staff", staff_password),
        ("CAMPUS-2001", "campus_student", "Demo Student", "student", student_password),
    ]

    added_count = 0

    try:
        # Repeated setup adds missing identities without resetting existing ones.
        for campus_id, username, name, affiliation, password in accounts:
            existing = connection.execute(
                "SELECT campus_id FROM campus_accounts WHERE campus_id = ?",
                (campus_id,),
            ).fetchone()

            if existing is not None:
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
        # Undo this call's inserts if an insert or hashing operation fails.
        connection.rollback()
        raise
    finally:
        connection.close()

    return added_count


def seed_campus_accounts_from_environment(database_path):
    # Read setup passwords without putting their values in source code or output.
    staff_password = os.environ.get("CAMPUS_FAKE_STAFF_PASSWORD", "")
    student_password = os.environ.get("CAMPUS_FAKE_STUDENT_PASSWORD", "")

    if not staff_password or not student_password:
        raise RuntimeError(
            "Set CAMPUS_FAKE_STAFF_PASSWORD and CAMPUS_FAKE_STUDENT_PASSWORD."
        )

    return seed_campus_accounts(
        database_path,
        staff_password,
        student_password,
    )


def find_campus_identity(username, password, database_path=None):
    # Use the shared database location unless a test supplies a temporary path.
    from backend.auth.database import DB_FILE

    if database_path is None:
        database_path = DB_FILE

    # Authentication reads existing data without creating or updating a database.
    database_uri = Path(database_path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(database_uri, uri=True)
    connection.row_factory = sqlite3.Row

    try:
        # Search campus accounts only and pass the username as a SQL parameter.
        account = connection.execute(
            """
            SELECT campus_id, username, name, affiliation, password_hash
            FROM campus_accounts
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
    finally:
        connection.close()

    # Unknown usernames and incorrect passwords produce the same failure result.
    if account is None:
        return None

    if not verify_password(account["password_hash"], password):
        return None

    # Return identity information without credentials or staff-site permissions.
    return {
        "campus_id": account["campus_id"],
        "username": account["username"],
        "name": account["name"],
        "affiliation": account["affiliation"],
    }


def test_create_campus_table_preserves_staff(tmp_path):
    # Use a disposable database containing an unrelated staff record.
    database_path = tmp_path / "campus_table_test.db"
    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (1, "staff_fixture", "test-placeholder-not-a-login-hash"),
        )
        connection.commit()
    finally:
        connection.close()

    # Setup must be repeatable without removing staff data.
    create_campus_table(database_path)
    create_campus_table(database_path)

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

    assert [column[1] for column in columns] == [
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


def test_seed_campus_accounts_preserves_existing_data(tmp_path):
    # Create a temporary staff table before adding independent campus identities.
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

    staff_password = "Test-Staff-Only!"
    student_password = "Test-Student-Only!"

    added_count = seed_campus_accounts(
        database_path, staff_password, student_password
    )

    # Different inputs on a second run must not replace existing passwords.
    repeated_count = seed_campus_accounts(
        database_path,
        "Different-Staff-Test!",
        "Different-Student-Test!",
    )

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

    # Verify hashes and prove that repeated seeding preserved both passwords.
    assert campus_rows[0][4] != staff_password
    assert campus_rows[1][4] != student_password
    assert verify_password(campus_rows[0][4], staff_password)
    assert verify_password(campus_rows[1][4], student_password)
    assert not verify_password(campus_rows[0][4], "Different-Staff-Test!")
    assert not verify_password(campus_rows[1][4], "Different-Student-Test!")


def test_campus_seed_requires_environment_passwords(tmp_path, monkeypatch):
    # Missing environment passwords must fail without creating a database.
    import pytest

    monkeypatch.delenv("CAMPUS_FAKE_STAFF_PASSWORD", raising=False)
    monkeypatch.delenv("CAMPUS_FAKE_STUDENT_PASSWORD", raising=False)
    database_path = tmp_path / "must_not_be_created.db"

    with pytest.raises(RuntimeError, match="CAMPUS_FAKE_STAFF_PASSWORD"):
        seed_campus_accounts_from_environment(database_path)

    assert not database_path.exists()


def test_database_campus_lookup(tmp_path):
    # Keep all authentication fixtures separate from the real users.db.
    database_path = tmp_path / "campus_lookup_test.db"
    staff_only_password = "Staff-Only-Test!"
    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (1, "staff_test", hash_password(staff_only_password)),
        )
        connection.commit()
    finally:
        connection.close()

    staff_password = "Campus-Staff-Test!"
    student_password = "Campus-Student-Test!"
    seed_campus_accounts(database_path, staff_password, student_password)

    # Both affiliations authenticate, but returned identities contain no roles.
    staff = find_campus_identity("campus_staff", staff_password, database_path)
    student = find_campus_identity(
        "campus_student", student_password, database_path
    )

    assert staff == {
        "campus_id": "CAMPUS-1001",
        "username": "campus_staff",
        "name": "Demo Staff",
        "affiliation": "staff",
    }
    assert student == {
        "campus_id": "CAMPUS-2001",
        "username": "campus_student",
        "name": "Demo Student",
        "affiliation": "student",
    }

    for identity in (staff, student):
        assert "password" not in identity
        assert "password_hash" not in identity
        assert "role" not in identity

    # Refuse wrong passwords, unknown usernames, and staff-table-only accounts.
    assert find_campus_identity(
        "campus_staff", "wrong-password", database_path
    ) is None
    assert find_campus_identity(
        "unknown_account", staff_password, database_path
    ) is None
    assert find_campus_identity(
        "staff_test", staff_only_password, database_path
    ) is None

    # A username change must preserve the campus ID and invalidate the old name.
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "UPDATE campus_accounts SET username = ? WHERE campus_id = ?",
            ("renamed_staff", "CAMPUS-1001"),
        )
        connection.commit()
    finally:
        connection.close()

    renamed = find_campus_identity(
        "renamed_staff", staff_password, database_path
    )
    assert renamed is not None
    assert renamed["campus_id"] == "CAMPUS-1001"
    assert find_campus_identity(
        "campus_staff", staff_password, database_path
    ) is None


def test_database_lookup_does_not_create_missing_database(tmp_path):
    # A wrong database path must fail instead of silently creating an empty file.
    import pytest

    database_path = tmp_path / "missing_database.db"

    with pytest.raises(sqlite3.OperationalError):
        find_campus_identity("campus_staff", "test-password", database_path)

    assert not database_path.exists()