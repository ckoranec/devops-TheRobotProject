from venv import create

from backend.auth.database import DB_FILE, create_staff_campus_mapping
from backend.auth.seed_users import create_users_table
from backend.auth.campus_directory import create_campus_table

def initiliaze_database():
    # Creates the staff users table
    create_users_table()

    # Creates the campus accounts table
    create_campus_table((DB_FILE))

    # Creates the mapping table
    print("Database tales initliazed succesfully.")

if __name__ == "__main__":
    initiliaze_database()