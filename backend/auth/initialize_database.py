
from backend.auth.database import DB_FILE, create_staff_campus_mapping
from backend.auth.seed_users import create_users_table
from backend.auth.campus_directory import create_campus_table

def initialize_database():
    # Creates the staff users table
    create_users_table()

    # Creates the campus accounts table
    create_campus_table(DB_FILE)

    # Creates the mapping table
    create_staff_campus_mapping()
    print("Database tables initialized successfully.")

if __name__ == "__main__":
    initialize_database()