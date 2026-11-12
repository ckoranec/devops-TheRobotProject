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