from backend.auth.database import DB_FILE, create_staff_campus_mapping, get_user_by_username, get_db_connection
from backend.auth.seed_users import create_users_table, seed_database
from backend.auth.campus_directory import (
    create_campus_table,
    seed_campus_accounts_from_environment
)

def seed_staff_campus_mapping():
    # Finds the staff account using its username
    user = get_user_by_username("staff_test")

    # Stops if the staff account doesn't exist
    if user is None:
        raise RuntimeError("Cannot complete seed, staff_test doesn't exist.")

    # Retrieves the numeric staff ID
    staff_id = user[0]

    # Connect to the database
    conn = get_db_connection()

    try:
        # Inserts the mapping only if it doesn't exist already
        conn.execute(
            """
            INSERT INTO staff_campus_mapping
                (campus_id, staff_user_id)
            VALUES (?, ?)
            """,
            ("CAMPUS-1001", staff_id)
        )

        # Checks that the campus account maps to the correct staff ID
        result = conn.execute(
            """
            SELECT staff_user_id
            FROM staff_campus_mapping
            WHERE campus_id = ?
            """,
            ("CAMPUS-1001",)
        ).fetchone()

        if result is None or result[0] != staff_id:
            raise RuntimeError("Campus-to-staff mapping conflict detected.")

        conn.commit()

    finally:
        conn.close()

def initialize_database():
    # Create the staff users table
    create_users_table()

    # Create the campus accounts table
    create_campus_table(DB_FILE)

    # Create the mapping table
    create_staff_campus_mapping()

    # Ensures the fixed staff test account exists
    seed_database(num_users=0)

    # Makes sure the campus accounts exist
    seed_campus_accounts_from_environment(DB_FILE)

    # Links the campus staff account to our staff login system
    seed_staff_campus_mapping()

    print("Database tables initialized successfully.")

if __name__ == "__main__":
    initialize_database()